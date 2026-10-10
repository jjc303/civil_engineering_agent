from __future__ import annotations

import sys
from types import SimpleNamespace

import pytest
from sqlalchemy import select

from agent.api.knowledge import router as knowledge_router
from agent.core.config import Settings
from agent.db.base import Database
from agent.db.models import KnowledgeDocumentVersionModel
from agent.rag.chroma_adapter import DashScopeEmbeddingFunction
from agent.services.knowledge_service import KnowledgeService


def _runtime_settings(**overrides: object) -> Settings:
    return Settings(
        database_url="sqlite+pysqlite:///:memory:",
        internal_perception_token="test",
        llm_provider="fake",
        bind_host="testserver",
        port=8000,
        cors_origins=("http://testserver",),
        **overrides,
    )


def test_dashscope_rag_requires_an_api_key_when_enabled() -> None:
    settings = _runtime_settings(rag_enabled=True)

    with pytest.raises(RuntimeError, match="AGENT_RAG_EMBEDDING_API_KEY"):
        settings.validate_for_runtime()


def test_dashscope_rag_accepts_text_embedding_v4_configuration() -> None:
    settings = _runtime_settings(
        rag_enabled=True,
        rag_embedding_api_key="test-key-not-used-for-network",
        rag_embedding_base_url="https://workspace.cn-beijing.maas.aliyuncs.com/compatible-mode/v1",
        rag_embedding_dimensions=1024,
    )

    settings.validate_for_runtime()


def test_dashscope_embedding_function_batches_and_preserves_response_order(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[dict[str, object]] = []

    class FakeEmbeddings:
        def create(self, **kwargs: object) -> SimpleNamespace:
            calls.append(kwargs)
            items = list(kwargs["input"])
            # The API is allowed to return results out of order; the adapter must
            # restore the input order before returning them to Chroma.
            return SimpleNamespace(data=[SimpleNamespace(index=index, embedding=[float(index)]) for index in reversed(range(len(items)))])

    class FakeOpenAI:
        def __init__(self, **kwargs: object) -> None:
            self.embeddings = FakeEmbeddings()

    monkeypatch.setitem(sys.modules, "openai", SimpleNamespace(OpenAI=FakeOpenAI))
    embed = DashScopeEmbeddingFunction("key", "https://example.invalid/v1", "text-embedding-v4", 1024)

    vectors = embed([f"chunk-{index}" for index in range(11)])

    assert [len(call["input"]) for call in calls] == [10, 1]
    assert all(call["dimensions"] == 1024 for call in calls)
    assert vectors == [[float(index)] for index in range(10)] + [[0.0]]


def test_knowledge_inbox_indexes_new_and_changed_files(tmp_path) -> None:
    class FakeRetriever:
        def __init__(self) -> None:
            self.versions: dict[str, list[dict[str, object]]] = {}

        def replace_version(self, version_id: str, chunks: list[dict[str, object]]) -> None:
            self.versions[version_id] = chunks

        def delete_version(self, version_id: str) -> None:
            self.versions.pop(version_id, None)

        def count(self) -> int:
            return sum(len(chunks) for chunks in self.versions.values())

    database = Database("sqlite+pysqlite:///:memory:")
    database.create_schema()
    inbox = tmp_path / "to-index"
    original = inbox / "accident_reports" / "安全规范.md"
    original.parent.mkdir(parents=True)
    original.write_text("高处作业必须佩戴安全带。", encoding="utf-8")
    retriever = FakeRetriever()
    service = KnowledgeService(
        database, retriever, str(tmp_path / "managed"), str(inbox),
        1024 * 1024, ".md,.txt", 800, 120, 8,
    )

    assert service.sync_inbox() == {"imported": 1, "recovered": 0, "retried": 0, "skipped": 0, "failed": 0, "summaries_generated": 0}
    assert service.sync_inbox() == {"imported": 0, "recovered": 0, "retried": 0, "skipped": 1, "failed": 0, "summaries_generated": 0}
    assert len(retriever.versions) == 1

    original.write_text("高处作业必须佩戴安全带，并设置防护栏。", encoding="utf-8")

    assert service.sync_inbox() == {"imported": 1, "recovered": 0, "retried": 0, "skipped": 0, "failed": 0, "summaries_generated": 0}
    assert len(retriever.versions) == 1
    page = service.list_documents(20, 0, None)
    assert len(page.items) == 1
    assert page.items[0].current_version == 2

    retriever.versions.clear()

    assert service.sync_inbox() == {"imported": 0, "recovered": 1, "retried": 0, "skipped": 1, "failed": 0, "summaries_generated": 0}
    assert len(retriever.versions) == 1


def test_knowledge_inbox_restores_a_missing_managed_original_before_retrying(tmp_path) -> None:
    class FakeRetriever:
        def __init__(self) -> None:
            self.versions: dict[str, list[dict[str, object]]] = {}

        def replace_version(self, version_id: str, chunks: list[dict[str, object]]) -> None:
            self.versions[version_id] = chunks

        def delete_version(self, version_id: str) -> None:
            self.versions.pop(version_id, None)

        def count(self) -> int:
            return sum(len(chunks) for chunks in self.versions.values())

    database = Database("sqlite+pysqlite:///:memory:")
    database.create_schema()
    inbox, managed = tmp_path / "to-index", tmp_path / "managed"
    original = inbox / "accident_reports" / "规程.md"
    original.parent.mkdir(parents=True)
    original.write_text("必须执行班前安全检查。", encoding="utf-8")
    service = KnowledgeService(database, FakeRetriever(), str(managed), str(inbox), 1024 * 1024, ".md", 800, 120, 8)
    service.sync_inbox()
    with database.session() as session:
        version = session.scalar(select(KnowledgeDocumentVersionModel))
        version.status = "FAILED"
        storage_path = managed / version.storage_key
    storage_path.unlink()

    assert service.sync_inbox() == {"imported": 0, "recovered": 0, "retried": 1, "skipped": 0, "failed": 0, "summaries_generated": 0}
    assert storage_path.read_text(encoding="utf-8") == "必须执行班前安全检查。"


def test_knowledge_api_does_not_require_an_administrator_token() -> None:
    assert knowledge_router.dependencies == []
