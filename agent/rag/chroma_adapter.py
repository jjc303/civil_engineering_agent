from __future__ import annotations

from collections.abc import Callable
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
    source_label: str = ""
    document_type: str = "ACCIDENT_REPORT"


class DashScopeEmbeddingFunction:
    """Chroma embedding function backed by Alibaba Cloud Model Studio's OpenAI API."""

    _MAX_BATCH_SIZE = 10  # text-embedding-v4's documented request limit.

    def __init__(self, api_key: str, base_url: str, model: str, dimensions: int, *, batch_size: int = _MAX_BATCH_SIZE) -> None:
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise RuntimeError("DashScope RAG requires the openai package") from exc
        self._client = OpenAI(api_key=api_key, base_url=base_url)
        self._model = model
        self._dimensions = dimensions
        self._batch_size = max(1, batch_size)

    # Chroma validates that the single argument is named `input`.
    def __call__(self, input: Sequence[str]) -> list[list[float]]:
        vectors: list[list[float]] = []
        values = list(input)
        for start in range(0, len(values), self._batch_size):
            kwargs: dict[str, Any] = {
                "model": self._model,
                "input": values[start : start + self._batch_size],
                "encoding_format": "float",
            }
            if self._dimensions > 0:
                kwargs["dimensions"] = self._dimensions
            response = self._client.embeddings.create(**kwargs)
            vectors.extend(list(item.embedding) for item in sorted(response.data, key=lambda item: item.index))
        return vectors


@dataclass(frozen=True)
class EmbeddingProviderSpec:
    name: str
    build_function: Callable[[str, str, str, int], Any]
    default_collection: Callable[[str, int], str]
    validator: Callable[[str, str, str, int, bool], None] | None = None


def _validate_dashscope(model: str, api_key: str, base_url: str, dimensions: int, rag_enabled: bool) -> None:
    if model != "text-embedding-v4":
        raise RuntimeError("AGENT_RAG_EMBEDDING_MODEL must be text-embedding-v4 for the dashscope provider")
    if dimensions not in {64, 128, 256, 512, 768, 1024, 1536, 2048}:
        raise RuntimeError("AGENT_RAG_EMBEDDING_DIMENSIONS is not supported by text-embedding-v4")
    if rag_enabled and not api_key:
        raise RuntimeError("AGENT_RAG_EMBEDDING_API_KEY or DASHSCOPE_API_KEY must be configured when RAG is enabled")
    if rag_enabled and not base_url:
        raise RuntimeError("AGENT_RAG_EMBEDDING_BASE_URL must be configured when RAG is enabled")


def _validate_openai_compatible(model: str, api_key: str, base_url: str, dimensions: int, rag_enabled: bool) -> None:
    if not model.strip():
        raise RuntimeError("AGENT_RAG_EMBEDDING_MODEL must be configured")
    if dimensions < 0:
        raise RuntimeError("AGENT_RAG_EMBEDDING_DIMENSIONS must be non-negative")
    if rag_enabled and not api_key:
        raise RuntimeError("AGENT_RAG_EMBEDDING_API_KEY must be configured when RAG is enabled")
    if rag_enabled and not base_url:
        raise RuntimeError("AGENT_RAG_EMBEDDING_BASE_URL must be configured when RAG is enabled")


def _build_sentence_transformer(model: str, _api_key: str, _base_url: str, _dimensions: int) -> Any:
    try:
        from chromadb.utils.embedding_functions import SentenceTransformerEmbeddingFunction
    except ImportError as exc:
        raise RuntimeError("Local RAG requires sentence-transformers") from exc
    return SentenceTransformerEmbeddingFunction(model_name=model)


_EMBEDDING_PROVIDERS: dict[str, EmbeddingProviderSpec] = {
    "dashscope": EmbeddingProviderSpec(
        name="dashscope",
        build_function=lambda model, api_key, base_url, dimensions: DashScopeEmbeddingFunction(
            api_key, base_url, model, dimensions
        ),
        default_collection=lambda _model, dimensions: f"safety_knowledge_qwen_v4_{dimensions}",
        validator=_validate_dashscope,
    ),
    "sentence_transformers": EmbeddingProviderSpec(
        name="sentence_transformers",
        build_function=_build_sentence_transformer,
        default_collection=lambda _model, _dimensions: "safety_knowledge_v1",
        validator=None,
    ),
    "openai_compatible": EmbeddingProviderSpec(
        name="openai_compatible",
        build_function=lambda model, api_key, base_url, dimensions: DashScopeEmbeddingFunction(
            api_key, base_url, model, dimensions, batch_size=32
        ),
        default_collection=lambda model, dimensions: f"safety_knowledge_{model.replace('/', '_')}_{dimensions}",
        validator=_validate_openai_compatible,
    ),
}


def register_embedding_provider(name: str, spec: EmbeddingProviderSpec) -> None:
    """Register a custom RAG embedding provider at runtime."""
    _EMBEDDING_PROVIDERS[name.lower()] = spec


def supported_embedding_providers() -> frozenset[str]:
    return frozenset(_EMBEDDING_PROVIDERS)


def validate_embedding_settings(
    provider: str,
    model: str,
    api_key: str,
    base_url: str,
    dimensions: int,
    rag_enabled: bool,
) -> None:
    spec = _EMBEDDING_PROVIDERS.get(provider.lower())
    if spec is None:
        supported = ", ".join(sorted(_EMBEDDING_PROVIDERS))
        raise RuntimeError(f"AGENT_RAG_EMBEDDING_PROVIDER must be one of: {supported}")
    if spec.validator is not None:
        spec.validator(model, api_key, base_url, dimensions, rag_enabled)


class ChromaKnowledgeRetriever:
    """A fixed local Chroma collection; callers never supply paths or filters."""

    def __init__(
        self,
        persist_directory: str,
        embedding_provider: str,
        embedding_model: str,
        embedding_api_key: str = "",
        embedding_base_url: str = "",
        embedding_dimensions: int = 1024,
        *,
        collection_name: str = "",
    ) -> None:
        try:
            import chromadb
        except ImportError as exc:  # optional at import time, mandatory when RAG is enabled
            raise RuntimeError("RAG requires chromadb") from exc

        spec = _EMBEDDING_PROVIDERS.get(embedding_provider.lower())
        if spec is None:
            raise RuntimeError(f"Unsupported RAG embedding provider: {embedding_provider}")

        embedding_function = spec.build_function(
            embedding_model,
            embedding_api_key,
            embedding_base_url,
            embedding_dimensions,
        )
        resolved_collection = collection_name.strip() or spec.default_collection(
            embedding_model,
            embedding_dimensions,
        )

        Path(persist_directory).mkdir(parents=True, exist_ok=True)
        self._client = chromadb.PersistentClient(path=persist_directory)
        self._collection = self._client.get_or_create_collection(
            resolved_collection,
            embedding_function=embedding_function,
        )
        self._standards = self._client.get_or_create_collection("standards", embedding_function=embedding_function)

    def replace_version(self, version_id: str, chunks: list[dict[str, Any]]) -> None:
        self._replace(self._collection, version_id, chunks)

    def delete_version(self, version_id: str) -> None:
        self._collection.delete(where={"document_version_id": version_id})

    def replace_standard_version(self, version_id: str, chunks: list[dict[str, Any]]) -> None:
        self._replace(self._standards, version_id, chunks)

    @staticmethod
    def _replace(collection: Any, version_id: str, chunks: list[dict[str, Any]]) -> None:
        collection.delete(where={"document_version_id": version_id})
        if chunks:
            collection.add(ids=[c["chunk_id"] for c in chunks], documents=[c["text"] for c in chunks], metadatas=[c["metadata"] for c in chunks])

    def delete_standard_version(self, version_id: str) -> None:
        self._standards.delete(where={"document_version_id": version_id})

    def update_version_source(self, document_type: str, version_id: str, source_label: str) -> None:
        collection = self._standards if document_type == "STANDARD" else self._collection
        result = collection.get(where={"document_version_id": version_id}, include=["metadatas"])
        ids = result.get("ids", [])
        if ids:
            collection.update(ids=ids, metadatas=[{**(meta or {}), "source_label": source_label} for meta in result["metadatas"]])

    def count_standards(self) -> int:
        return int(self._standards.count())

    def count(self) -> int:
        """Return the number of persisted chunks in the fixed collection."""
        return int(self._collection.count())

    def search(self, query: str, top_k: int) -> list[KnowledgeChunk]:
        return self._search_collection(self._collection, query, top_k)

    def search_standards(self, query: str, top_k: int) -> list[KnowledgeChunk]:
        return self._search_collection(self._standards, query, top_k)

    def search_active(self, document_type: str, query: str, top_k: int, version_ids: list[str]) -> list[KnowledgeChunk]:
        if not version_ids:
            return []
        collection = self._standards if document_type == "STANDARD" else self._collection
        return self._search_collection(collection, query, top_k, where={"document_version_id": {"$in": version_ids}})

    def get_version(self, document_type: str, version_id: str) -> list[KnowledgeChunk]:
        collection = self._standards if document_type == "STANDARD" else self._collection
        result = collection.get(where={"document_version_id": version_id}, include=["documents", "metadatas"])
        rows: list[tuple[int, KnowledgeChunk]] = []
        for position, (chunk_id, body, meta) in enumerate(zip(result.get("ids", []), result.get("documents", []), result.get("metadatas", []))):
            if not meta:
                continue
            rows.append((int(meta.get("chunk_index", position)), KnowledgeChunk(str(chunk_id), str(body), str(meta["document_id"]), str(meta["document_version_id"]), int(meta["version_no"]), str(meta["title"]), str(meta["page_or_section"]), 1.0, str(meta.get("source_label", "")), document_type)))
        return [chunk for _, chunk in sorted(rows, key=lambda pair: pair[0])]

    @staticmethod
    def _search_collection(collection: Any, query: str, top_k: int, where: dict[str, Any] | None = None) -> list[KnowledgeChunk]:
        if collection.count() == 0:
            return []
        result = collection.query(query_texts=[query], n_results=top_k, where=where or {"status": "ACTIVE"})
        ids, docs, metas, distances = (result.get("ids", [[]])[0], result.get("documents", [[]])[0], result.get("metadatas", [[]])[0], result.get("distances", [[]])[0])
        return [KnowledgeChunk(str(chunk_id), str(text), str(meta["document_id"]), str(meta["document_version_id"]), int(meta["version_no"]), str(meta["title"]), str(meta["page_or_section"]), max(0.0, min(1.0, 1.0 - float(distance))), str(meta.get("source_label", "")), str(meta.get("document_type", "ACCIDENT_REPORT"))) for chunk_id, text, meta, distance in zip(ids, docs, metas, distances)]
