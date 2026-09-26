from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


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


class ChromaKnowledgeRetriever:
    """A fixed local Chroma collection; callers never supply paths or filters."""

    def __init__(self, persist_directory: str, embedding_model: str) -> None:
        try:
            import chromadb
            from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
        except ImportError as exc:  # optional at import time, mandatory when RAG is enabled
            raise RuntimeError("RAG requires chromadb and sentence-transformers") from exc
        Path(persist_directory).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=persist_directory)
        self._collection = self._client.get_or_create_collection(
            "safety_knowledge_v1",
            embedding_function=SentenceTransformerEmbeddingFunction(model_name=embedding_model),
        )

    def replace_version(self, version_id: str, chunks: list[dict[str, Any]]) -> None:
        self._collection.delete(where={"document_version_id": version_id})
        if chunks:
            self._collection.add(ids=[c["chunk_id"] for c in chunks], documents=[c["text"] for c in chunks], metadatas=[c["metadata"] for c in chunks])

    def delete_version(self, version_id: str) -> None:
        self._collection.delete(where={"document_version_id": version_id})

    def search(self, query: str, top_k: int) -> list[KnowledgeChunk]:
        result = self._collection.query(query_texts=[query], n_results=top_k, where={"status": "ACTIVE"})
        ids, docs, metas, distances = (result.get("ids", [[]])[0], result.get("documents", [[]])[0], result.get("metadatas", [[]])[0], result.get("distances", [[]])[0])
        return [KnowledgeChunk(str(chunk_id), str(text), str(meta["document_id"]), str(meta["document_version_id"]), int(meta["version_no"]), str(meta["title"]), str(meta["page_or_section"]), max(0.0, min(1.0, 1.0 - float(distance)))) for chunk_id, text, meta, distance in zip(ids, docs, metas, distances)]
