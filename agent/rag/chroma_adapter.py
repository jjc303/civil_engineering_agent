from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Sequence


@dataclass(frozen=True)
class KnowledgeChunk:
    chunk_id: str
    text: str
    document_id: str
    document_version_id: str
    version_no: int
    title: str
    page_or_section: str
    relevance_score: float


class DashScopeEmbeddingFunction:
    """Chroma embedding function backed by Alibaba Cloud Model Studio's OpenAI API."""

    _MAX_BATCH_SIZE = 10  # text-embedding-v4's documented request limit.

    def __init__(self, api_key: str, base_url: str, model: str, dimensions: int) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("DashScope RAG requires the openai package") from exc
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._dimensions = dimensions

    # Chroma validates that the single argument is named `input`.
    def __call__(self, input: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        values = list(input)
        for start in range(0, len(values), self._MAX_BATCH_SIZE):
            response = self._client.embeddings.create(
                model=self._model,
                input=values[start : start + self._MAX_BATCH_SIZE],
                dimensions=self._dimensions,
                encoding_format="float",
            )
            vectors.extend(list(item.embedding) for item in sorted(response.data, key=lambda item: item.index))
        return vectors


class ChromaKnowledgeRetriever:
    """A fixed local Chroma collection; callers never supply paths or filters."""

    def __init__(self, persist_directory: str, embedding_provider: str, embedding_model: str, embedding_api_key: str = "", embedding_base_url: str = "", embedding_dimensions: int = 1024) -> None:
        try:
            import chromadb
        except ImportError as exc:  # optional at import time, mandatory when RAG is enabled
            raise RuntimeError("RAG requires chromadb") from exc

        if embedding_provider == "dashscope":
            embedding_function = DashScopeEmbeddingFunction(
                embedding_api_key, embedding_base_url, embedding_model, embedding_dimensions
            )
            # Do not reuse the old local-model collection: embedding dimensions and
            # vector spaces differ, so its contents must be re-indexed.
            collection_name = f"safety_knowledge_qwen_v4_{embedding_dimensions}"
        elif embedding_provider == "sentence_transformers":
            try:
                from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
            except ImportError as exc:
                raise RuntimeError("Local RAG requires sentence-transformers") from exc
            embedding_function = SentenceTransformerEmbeddingFunction(model_name=embedding_model)
            collection_name = "safety_knowledge_v1"
        else:
            raise RuntimeError(f"Unsupported RAG embedding provider: {embedding_provider}")

        Path(persist_directory).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=persist_directory)
        self._collection = self._client.get_or_create_collection(
            collection_name,
            embedding_function=embedding_function,
        )

    def replace_version(self, version_id: str, chunks: list[dict[str, Any]]) -> None:
        self._collection.delete(where={"document_version_id": version_id})
        if chunks:
            self._collection.add(ids=[c["chunk_id"] for c in chunks], documents=[c["text"] for c in chunks], metadatas=[c["metadata"] for c in chunks])

    def delete_version(self, version_id: str) -> None:
        self._collection.delete(where={"document_version_id": version_id})

    def count(self) -> int:
        """Return the number of persisted chunks in the fixed collection."""
        return int(self._collection.count())

    def search(self, query: str, top_k: int) -> list[KnowledgeChunk]:
        result = self._collection.query(query_texts=[query], n_results=top_k, where={"status": "ACTIVE"})
        ids, docs, metas, distances = (result.get("ids", [[]])[0], result.get("documents", [[]])[0], result.get("metadatas", [[]])[0], result.get("distances", [[]])[0])
        return [KnowledgeChunk(str(chunk_id), str(text), str(meta["document_id"]), str(meta["document_version_id"]), int(meta["version_no"]), str(meta["title"]), str(meta["page_or_section"]), max(0.0, min(1.0, 1.0 - float(distance)))) for chunk_id, text, meta, distance in zip(ids, docs, metas, distances)]
