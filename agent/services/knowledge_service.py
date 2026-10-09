from __future__ import annotations

import hashlib
import logging
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, select

from agent.contracts.chat import KnowledgeCitation
from agent.core.config import (
    DEFAULT_RAG_ACCIDENT_REPORTS_SUBDIRECTORY,
    DEFAULT_RAG_STANDARDS_SUBDIRECTORY,
    validate_rag_inbox_subdirectories,
)
from agent.contracts.knowledge import (
    DocumentType, StandardValidity, KnowledgeMetadataUpdate, KnowledgeDocumentDetailResponse, KnowledgeDocumentPage, KnowledgeDocumentResponse,
    KnowledgeIndexJobPage, KnowledgeIndexJobResponse, KnowledgeVersionResponse,
)
from agent.db.base import Database
from agent.db.models import KnowledgeAuditModel, KnowledgeDocumentModel, KnowledgeDocumentVersionModel, KnowledgeIndexJobModel
from agent.llm.protocol import ChatModelPort
from agent.rag.chroma_adapter import ChromaKnowledgeRetriever
from agent.rag.manager import RagManager

logger = logging.getLogger(__name__)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class KnowledgeService:
    def __init__(self, database: Database, retriever: ChromaKnowledgeRetriever | None, document_directory: str, inbox_directory: str, max_upload_bytes: int, allowed_extensions: str, chunk_size: int, chunk_overlap: int, top_k_max: int, *, standards_subdirectory: str = DEFAULT_RAG_STANDARDS_SUBDIRECTORY, accident_reports_subdirectory: str = DEFAULT_RAG_ACCIDENT_REPORTS_SUBDIRECTORY) -> None:
        validate_rag_inbox_subdirectories(standards_subdirectory, accident_reports_subdirectory)
        self.database, self.retriever = database, retriever
        self.rag_manager = RagManager(retriever, chunk_size, chunk_overlap) if retriever else None
        self.root = Path(document_directory)
        self.inbox = Path(inbox_directory)
        self.inbox_subdirectories: dict[DocumentType, str] = {
            "STANDARD": standards_subdirectory,
            "ACCIDENT_REPORT": accident_reports_subdirectory,
        }
        self._document_type_by_subdirectory: dict[str, DocumentType] = {
            subdirectory: document_type for document_type, subdirectory in self.inbox_subdirectories.items()
        }
        self.max_upload_bytes = max_upload_bytes
        self.allowed = {value.strip().lower() for value in allowed_extensions.split(",")}
        self.chunk_size, self.chunk_overlap, self.top_k_max = chunk_size, chunk_overlap, top_k_max
        # A failed external embedding request should be retried after a process
        # restart, but never hammered once per inbox polling interval.
        self._failed_retry_attempted: set[str] = set()
        self.summary_model: ChatModelPort | None = None
        self._summary_failed_attempted: set[str] = set()

    def set_summary_model(self, model: ChatModelPort) -> None:
        self.summary_model = model

    def sync_inbox(self) -> dict[str, int]:
        """Index new files and repair a missing or failed local vector index."""
        if not self.retriever:
            raise RuntimeError("RAG is disabled")
        self.inbox.mkdir(parents=True, exist_ok=True)
        imported = recovered = retried = skipped = failed = 0

        # Chroma is a rebuildable cache. A cleared persistence directory must not
        # leave MySQL ACTIVE versions appearing searchable when no vectors exist.
        assert self.rag_manager is not None
        standards_count = self.rag_manager.count("STANDARD")
        report_count = self.rag_manager.count("ACCIDENT_REPORT")
        if report_count == 0 or standards_count == 0:
            with self.database.session() as session:
                missing_types = []
                if report_count == 0: missing_types.append("ACCIDENT_REPORT")
                if standards_count == 0: missing_types.append("STANDARD")
                active_version_ids = list(session.scalars(select(KnowledgeDocumentVersionModel.document_version_id).join(KnowledgeDocumentModel).where(KnowledgeDocumentVersionModel.status == "ACTIVE", KnowledgeDocumentModel.document_type.in_(missing_types))))
            for version_id in active_version_ids:
                try:
                    job = self.reindex(version_id, "recovery")
                    if job.status == "SUCCEEDED":
                        recovered += 1
                    else:
                        failed += 1
                except Exception:
                    failed += 1
                    logger.exception("Failed to restore missing Chroma index for version: %s", version_id)

        inbox_root = self.inbox.resolve()
        for path in sorted(self.inbox.rglob("*")):
            if not path.is_file() or path.is_symlink() or path.suffix.lower() not in self.allowed or path.name.lower() == "readme.md":
                continue
            try:
                resolved = path.resolve()
                relative = resolved.relative_to(inbox_root)
                if len(relative.parts) < 2 or relative.parts[0] not in self._document_type_by_subdirectory:
                    continue
                content = path.read_bytes()
                if not content or len(content) > self.max_upload_bytes:
                    raise ValueError("unsupported or oversized knowledge document")
                checksum = hashlib.sha256(content).hexdigest()
                source_label = f"inbox/{relative.as_posix()}"[:512]
                document_type = self._document_type_by_subdirectory[relative.parts[0]]
                with self.database.session() as session:
                    existing_version = session.scalar(select(KnowledgeDocumentVersionModel).where(KnowledgeDocumentVersionModel.checksum_sha256 == checksum))
                    existing = session.scalar(select(KnowledgeDocumentModel).where(KnowledgeDocumentModel.source_label == source_label))
                    document_id = existing.document_id if existing else None
                    current_version = existing.current_version if existing else None
                if existing_version:
                    with self.database.session() as session:
                        existing_doc = session.get(KnowledgeDocumentModel, existing_version.document_id)
                        if existing_doc.document_type != document_type:
                            skipped += 1
                            continue
                        prior_source = existing_doc.source_label
                    if existing_version.status == "ACTIVE":
                        if prior_source != source_label and prior_source.startswith("inbox/") and not (inbox_root / prior_source.removeprefix("inbox/")).exists():
                            self.rag_manager.update_version_source(document_type, existing_version.document_version_id, source_label)
                            with self.database.session() as session:
                                moved_doc = session.get(KnowledgeDocumentModel, existing_version.document_id)
                                if moved_doc.source_display == prior_source: moved_doc.source_display = source_label
                                moved_doc.source_label = source_label
                        skipped += 1
                        continue
                    if existing_version.document_version_id in self._failed_retry_attempted:
                        skipped += 1
                        continue
                    # The managed original is intentionally separate from the
                    # inbox. If it was removed along with a Chroma reset, restore
                    # it only after the inbox content matched the stored checksum.
                    managed_path = self.root / existing_version.storage_key
                    if not managed_path.is_file():
                        managed_path.parent.mkdir(parents=True, exist_ok=True)
                        managed_path.write_bytes(content)
                    job = self.reindex(existing_version.document_version_id, "inbox")
                    self._failed_retry_attempted.add(existing_version.document_version_id)
                    if job.status == "SUCCEEDED":
                        retried += 1
                    else:
                        failed += 1
                    continue
                self.upload(
                    filename=path.name,
                    content=content,
                    title=path.stem[:255] or path.name[:255],
                    source_label=source_label,
                    actor="inbox",
                    document_id=document_id,
                    expected_current_version=current_version,
                    document_type=document_type,
                )
                imported += 1
            except Exception:
                failed += 1
                logger.exception("Failed to import knowledge inbox file: %s", path)
        summaries = self.backfill_missing_summaries(limit=5)
        return {"imported": imported, "recovered": recovered, "retried": retried, "skipped": skipped, "failed": failed, "summaries_generated": summaries["generated"]}

    def upload(self, *, filename: str, content: bytes, title: str, source_label: str, actor: str, document_id: str | None = None, expected_current_version: int | None = None, document_type: DocumentType | None = None, document_date: datetime | None = None, risk_tags: list[str] | None = None, summary: str | None = None) -> tuple[KnowledgeDocumentDetailResponse, KnowledgeIndexJobResponse, bool]:
        suffix = Path(filename).suffix.lower()
        title = title.strip()
        source_label = source_label.strip()
        if not title or len(title) > 255 or not source_label or len(source_label) > 512:
            raise ValueError("document title or source is invalid")
        if risk_tags is not None:
            risk_tags = [tag.strip()[:64] for tag in risk_tags if tag.strip()][:20]
        summary = summary.strip()[:2000] if summary else None
        if document_type not in (None, "STANDARD", "ACCIDENT_REPORT"):
            raise ValueError("invalid document type")
        if suffix not in self.allowed or not content or len(content) > self.max_upload_bytes:
            raise ValueError("unsupported or oversized knowledge document")
        checksum = hashlib.sha256(content).hexdigest()
        with self.database.session() as session:
            existing = session.scalar(select(KnowledgeDocumentVersionModel).where(KnowledgeDocumentVersionModel.checksum_sha256 == checksum))
            if existing:
                existing_document = session.get(KnowledgeDocumentModel, existing.document_id)
                if document_type and existing_document.document_type != document_type:
                    raise ValueError("identical content exists under a different document type")
                return self._detail(session, existing.document_id), self._job_for_version(session, existing.document_version_id), True
            now = _now()
            if document_id:
                document = session.get(KnowledgeDocumentModel, document_id)
                if not document:
                    raise KeyError("knowledge document not found")
                if document_type is not None and document.document_type != document_type:
                    raise ValueError("document type cannot change between versions")
                document_type = document.document_type
                if expected_current_version is not None and document.current_version != expected_current_version:
                    raise RuntimeError("document version conflict")
                version_no = document.current_version + 1
            else:
                document_type = document_type or "ACCIDENT_REPORT"
                document_id, version_no = str(uuid4()), 1
                document = KnowledgeDocumentModel(document_id=document_id, title=title, source_label=source_label, source_display=source_label, document_type=document_type, checksum_sha256=checksum, current_version=version_no, status="UPLOADED", created_at_utc=now, created_by=actor, document_date=document_date, risk_tags=risk_tags or [], summary=summary)
                session.add(document)
            if version_no > 1:
                document.title = title
                if actor != "inbox" and source_label: document.source_display = source_label
                if document_date is not None: document.document_date = document_date
                if risk_tags is not None: document.risk_tags = risk_tags
                if summary is not None: document.summary = summary
            version_id = str(uuid4())
            storage_key = f"{document_id}/{version_id}{suffix}"
            path = self.root / storage_key
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)
            version = KnowledgeDocumentVersionModel(document_version_id=version_id, document_id=document_id, version_no=version_no, storage_key=storage_key, checksum_sha256=checksum, status="UPLOADED", created_at_utc=now, created_by=actor)
            job = KnowledgeIndexJobModel(job_id=str(uuid4()), document_version_id=version_id, operation="INDEX", status="QUEUED", attempt_count=0, requested_by=actor, created_at_utc=now)
            session.add_all([version, job])
            document.current_version = version_no
            self._audit(session, actor, "UPLOAD" if version_no == 1 else "NEW_VERSION", document_id, version_id, job.job_id, {"filename": Path(filename).name, "bytes": len(content)})
        self.run_job(job.job_id)
        with self.database.session() as session:
            indexed = session.get(KnowledgeIndexJobModel, job.job_id).status == "SUCCEEDED"
        if indexed and self.summary_model is not None:
            try:
                self.summarize_document(document_id)
            except Exception:
                logger.exception("Failed to generate summary for knowledge document: %s", document_id)
                self._summary_failed_attempted.add(document_id)
        with self.database.session() as session:
            return self._detail(session, document_id), self._job(session.get(KnowledgeIndexJobModel, job.job_id)), False

    def summarize_document(self, document_id: str, *, force: bool = False) -> KnowledgeDocumentDetailResponse:
        """Summarize indexed source text; retain a curator's existing summary unless forced."""
        if self.summary_model is None:
            raise RuntimeError("summary model is unavailable")
        with self.database.session() as session:
            doc = session.get(KnowledgeDocumentModel, document_id)
            if not doc or doc.status != "ACTIVE":
                raise KeyError("active knowledge document not found")
            if doc.summary and not force:
                return self._detail(session, document_id)
            title, document_type, validity_status = doc.title, doc.document_type, doc.validity_status
            current_version = doc.current_version
        chunks = self.document_chunks(document_id)
        if not chunks:
            raise ValueError("document has no indexed text to summarize")
        count = len(chunks)
        sample_indices = sorted(set([*range(min(4, count)), *range(max(0, count // 2 - 2), min(count, count // 2 + 2)), *range(max(0, count - 4), count)]))
        excerpts = [{"section": chunks[index].page_or_section, "text": chunks[index].text[:1000]} for index in sample_indices]
        payload = self.summary_model.generate_structured(
            "生成文档摘要，仅输出 JSON 对象 {\"summary\": \"...\"}。根据提供的原文片段，用 80 至 180 个汉字概括文档主题、主要风险或规范适用内容。不得把推测写成事故事实，不得编造标准名称、编号、条款或日期。规范有效性为 UNKNOWN 时不得称其为现行规范。片段不足时说明原文未提供的内容。",
            {"title": title, "document_type": document_type, "validity_status": validity_status, "excerpts": excerpts},
        )
        summary = str(payload.get("summary") or "").strip()
        if not summary:
            raise ValueError("summary model returned empty content")
        if len(summary) > 400:
            raise ValueError("summary model returned oversized content")
        with self.database.session() as session:
            doc = session.get(KnowledgeDocumentModel, document_id)
            if not doc or doc.status != "ACTIVE" or doc.current_version != current_version:
                raise RuntimeError("document changed during summary generation")
            if not doc.summary or force:
                doc.summary = summary
                self._audit(session, "agent", "SUMMARY_GENERATED", document_id, None, None, {"chars": len(summary)})
            session.flush()
            return self._detail(session, document_id)

    def backfill_missing_summaries(self, limit: int = 5) -> dict[str, int]:
        if self.summary_model is None or not self.rag_manager:
            return {"generated": 0, "failed": 0}
        with self.database.session() as session:
            ids = list(session.scalars(select(KnowledgeDocumentModel.document_id).where(
                KnowledgeDocumentModel.status == "ACTIVE",
                (KnowledgeDocumentModel.summary.is_(None)) | (KnowledgeDocumentModel.summary == ""),
            ).order_by(KnowledgeDocumentModel.created_at_utc)))
        generated = failed = 0
        for document_id in ids:
            if document_id in self._summary_failed_attempted:
                continue
            try:
                self.summarize_document(document_id)
                generated += 1
            except Exception:
                failed += 1
                self._summary_failed_attempted.add(document_id)
                logger.exception("Failed to backfill document summary: %s", document_id)
            if generated + failed >= limit:
                break
        return {"generated": generated, "failed": failed}

    def run_job(self, job_id: str) -> None:
        if not self.retriever:
            raise RuntimeError("RAG is disabled")
        assert self.rag_manager is not None
        with self.database.session() as session:
            job = session.get(KnowledgeIndexJobModel, job_id)
            if not job: raise KeyError("index job not found")
            version = session.get(KnowledgeDocumentVersionModel, job.document_version_id)
            document = session.get(KnowledgeDocumentModel, version.document_id)
            job.status, job.attempt_count, job.started_at_utc = "RUNNING", job.attempt_count + 1, _now()
            version.status = "PARSING"
            try:
                prepared = self.rag_manager.prepare(self.root / version.storage_key, document.document_type, {
                    "document_id": document.document_id,
                    "document_version_id": version.document_version_id,
                    "version_no": version.version_no,
                    "title": document.title,
                    "source_label": document.source_label,
                    "checksum_sha256": version.checksum_sha256,
                })
                version.status = "INDEXING"
                self.rag_manager.replace_version(document.document_type, version.document_version_id, prepared.records)
                # Only one version is searchable per document.
                for old in session.scalars(select(KnowledgeDocumentVersionModel).where(KnowledgeDocumentVersionModel.document_id == document.document_id, KnowledgeDocumentVersionModel.document_version_id != version.document_version_id, KnowledgeDocumentVersionModel.status == "ACTIVE")):
                    old.status, old.retired_at_utc = "RETIRED", _now(); self._delete_vectors(old.document_version_id, document.document_type)
                version.status, version.parser_name, version.page_count, version.indexed_at_utc = "ACTIVE", prepared.parser_name, prepared.page_count, _now()
                document.status = "ACTIVE"
                job.status, job.finished_at_utc = "SUCCEEDED", _now()
                self._audit(session, job.requested_by, "INDEX_SUCCEEDED", document.document_id, version.document_version_id, job.job_id, {"chunk_count": len(prepared.records)})
            except Exception as exc:
                logger.exception("Knowledge indexing failed for version: %s", version.document_version_id)
                try:
                    self._delete_vectors(version.document_version_id, document.document_type)
                except Exception:
                    logger.exception("Failed to remove incomplete vectors for version: %s", version.document_version_id)
                version.status, version.failure_code, version.failure_detail_safe = "FAILED", "INDEX_FAILED", str(exc)[:512]
                job.status, job.error_code, job.error_detail_safe, job.finished_at_utc = "FAILED", "INDEX_FAILED", str(exc)[:512], _now()

    def search(self, query: str, top_k: int) -> tuple[list[dict[str, str]], list[KnowledgeCitation]]:
        return self._search_type("ACCIDENT_REPORT", query, top_k)

    def search_standards(self, query: str, top_k: int) -> tuple[list[dict[str, str]], list[KnowledgeCitation]]:
        return self._search_type("STANDARD", query, top_k)

    def standard_catalog(self) -> list[tuple[str, str, StandardValidity]]:
        """List files in the standards inbox with their current index state."""
        folder = self.inbox / self.inbox_subdirectories["STANDARD"]
        if not folder.exists():
            return []
        with self.database.session() as session:
            rows = session.execute(
                select(KnowledgeDocumentModel.source_label, KnowledgeDocumentModel.validity_status, KnowledgeDocumentVersionModel.status, KnowledgeDocumentVersionModel.failure_detail_safe)
                .join(KnowledgeDocumentVersionModel)
                .where(
                    KnowledgeDocumentModel.document_type == "STANDARD",
                    KnowledgeDocumentVersionModel.version_no == KnowledgeDocumentModel.current_version,
                )
            )
            states = {
                row.source_label: ((
                    "已索引" if row.status == "ACTIVE" else
                    "需 OCR" if row.status == "FAILED" and "no indexable text" in (row.failure_detail_safe or "") else
                    "索引失败" if row.status == "FAILED" else "待索引"
                ), row.validity_status)
                for row in rows
            }
        return sorted(
            (
                path.stem,
                *states.get(
                    f"inbox/{path.relative_to(self.inbox).as_posix()}"[:512],
                    ("超过文件大小限制" if path.stat().st_size > self.max_upload_bytes else "待索引", "UNKNOWN"),
                ),
            )
            for path in folder.rglob("*")
            if path.is_file() and not path.is_symlink() and path.suffix.lower() in self.allowed and path.name.lower() != "readme.md"
        )

    def _search_type(self, document_type: DocumentType, query: str, top_k: int) -> tuple[list[dict[str, str]], list[KnowledgeCitation]]:
        if not self.rag_manager: raise RuntimeError("RAG is disabled")
        if not query.strip() or not 1 <= top_k <= self.top_k_max: raise ValueError("invalid knowledge query")
        with self.database.session() as session:
            query_active = select(KnowledgeDocumentVersionModel.document_id, KnowledgeDocumentVersionModel.document_version_id, KnowledgeDocumentModel.validity_status).join(KnowledgeDocumentModel).where(KnowledgeDocumentVersionModel.status == "ACTIVE", KnowledgeDocumentModel.document_type == document_type)
            if document_type == "STANDARD":
                query_active = query_active.where(KnowledgeDocumentModel.validity_status != "SUPERSEDED")
            active = {(row.document_id, row.document_version_id): row.validity_status for row in session.execute(query_active)}
        chunks = self.rag_manager.search(document_type, query.strip(), top_k, [version_id for _, version_id in active])
        chunks = [chunk for chunk in chunks if (chunk.document_id, chunk.document_version_id) in active]
        return ([{"content": c.text, "title": c.title, "page_or_section": c.page_or_section, "source_label": c.source_label, "validity_status": active[(c.document_id, c.document_version_id)]} for c in chunks], [self._citation(c) for c in chunks])

    @staticmethod
    def _citation(chunk) -> KnowledgeCitation:
        return KnowledgeCitation(document_id=chunk.document_id, version_no=chunk.version_no, title=chunk.title, page_or_section=chunk.page_or_section, chunk_id=chunk.chunk_id, relevance_score=chunk.relevance_score, source_label=chunk.source_label, document_type=chunk.document_type)

    def _delete_vectors(self, version_id: str, document_type: DocumentType) -> None:
        if self.rag_manager:
            self.rag_manager.delete_version(document_type, version_id)

    def list_documents(self, limit: int, offset: int, status: str | None, document_type: DocumentType | None = None) -> KnowledgeDocumentPage:
        with self.database.session() as session:
            q = select(KnowledgeDocumentModel)
            if status: q = q.where(KnowledgeDocumentModel.status == status)
            if document_type: q = q.where(KnowledgeDocumentModel.document_type == document_type)
            total = int(session.scalar(select(func.count()).select_from(q.subquery())) or 0)
            items = list(session.scalars(q.order_by(KnowledgeDocumentModel.created_at_utc.desc()).offset(offset).limit(limit)))
            return KnowledgeDocumentPage(items=[self._document(x) for x in items], total=total, limit=limit, offset=offset)

    def detail(self, document_id: str) -> KnowledgeDocumentDetailResponse:
        with self.database.session() as session: return self._detail(session, document_id)

    def update_metadata(self, document_id: str, payload: KnowledgeMetadataUpdate, actor: str) -> KnowledgeDocumentDetailResponse:
        with self.database.session() as session:
            doc = session.get(KnowledgeDocumentModel, document_id)
            if not doc: raise KeyError("knowledge document not found")
            doc.document_date = payload.document_date
            doc.risk_tags = [tag.strip()[:64] for tag in payload.risk_tags if tag.strip()][:20]
            doc.summary = payload.summary.strip()[:2000] if payload.summary else None
            doc.source_display = payload.source_display.strip()[:512] if payload.source_display else None
            self._audit(session, actor, "METADATA_UPDATED", document_id, None, None, {})
            return self._detail(session, document_id)

    def document_chunks(self, document_id: str) -> list:
        if not self.rag_manager: raise RuntimeError("RAG is disabled")
        with self.database.session() as session:
            doc = session.get(KnowledgeDocumentModel, document_id)
            if not doc or doc.status != "ACTIVE": raise KeyError("active knowledge document not found")
            if doc.document_type == "STANDARD" and doc.validity_status == "SUPERSEDED": raise ValueError("standard is superseded")
            version = session.scalar(select(KnowledgeDocumentVersionModel).where(KnowledgeDocumentVersionModel.document_id == document_id, KnowledgeDocumentVersionModel.status == "ACTIVE"))
            if not version: raise KeyError("active document version not found")
            document_type = doc.document_type
            version_id = version.document_version_id
        return self.rag_manager.get_version(document_type, version_id)

    def set_standard_validity(self, document_id: str, validity_status: StandardValidity, actor: str) -> KnowledgeDocumentDetailResponse:
        with self.database.session() as session:
            doc = session.get(KnowledgeDocumentModel, document_id)
            if not doc: raise KeyError("knowledge document not found")
            if doc.document_type != "STANDARD": raise ValueError("validity status applies only to standards")
            previous = doc.validity_status
            doc.validity_status = validity_status
            self._audit(session, actor, "STANDARD_VALIDITY_UPDATED", document_id, None, None, {"from": previous, "to": validity_status})
            return self._detail(session, document_id)

    def classify(self, document_id: str, document_type: DocumentType, actor: str) -> KnowledgeDocumentDetailResponse:
        """Move an existing document between collections and rebuild its active version."""
        with self.database.session() as session:
            doc = session.get(KnowledgeDocumentModel, document_id)
            if not doc: raise KeyError("knowledge document not found")
            if doc.document_type == document_type: return self._detail(session, document_id)
            old_type = doc.document_type
            versions = list(session.scalars(select(KnowledgeDocumentVersionModel).where(KnowledgeDocumentVersionModel.document_id == document_id, KnowledgeDocumentVersionModel.status == "ACTIVE")))
            for version in versions:
                self._delete_vectors(version.document_version_id, old_type)
                version.status = "UPLOADED"
            doc.document_type, doc.status = document_type, "UPLOADED"
            doc.validity_status = "UNKNOWN"
            self._audit(session, actor, "CLASSIFY", document_id, None, None, {"from": old_type, "to": document_type})
            target = session.scalar(select(KnowledgeDocumentVersionModel).where(KnowledgeDocumentVersionModel.document_id == document_id).order_by(KnowledgeDocumentVersionModel.version_no.desc()).limit(1))
            active_version_id = target.document_version_id if target else None
        if active_version_id:
            self.reindex(active_version_id, actor)
        return self.detail(document_id)

    def retire(self, document_id: str, actor: str) -> None:
        with self.database.session() as session:
            doc = session.get(KnowledgeDocumentModel, document_id)
            if not doc: raise KeyError("knowledge document not found")
            for version in session.scalars(select(KnowledgeDocumentVersionModel).where(KnowledgeDocumentVersionModel.document_id == document_id, KnowledgeDocumentVersionModel.status == "ACTIVE")):
                version.status, version.retired_at_utc = "RETIRED", _now()
                self._delete_vectors(version.document_version_id, doc.document_type)
            doc.status, doc.retired_at_utc = "RETIRED", _now(); self._audit(session, actor, "RETIRED", document_id, None, None, {})

    def activate(self, document_id: str, version_id: str, actor: str) -> KnowledgeIndexJobResponse:
        """Activate by rebuilding the selected retained version into the fixed collection."""
        with self.database.session() as session:
            doc = session.get(KnowledgeDocumentModel, document_id)
            version = session.get(KnowledgeDocumentVersionModel, version_id)
            if not doc or not version or version.document_id != document_id:
                raise KeyError("knowledge document version not found")
            version.status, version.failure_code, version.failure_detail_safe = "UPLOADED", None, None
            doc.status, doc.retired_at_utc = "UPLOADED", None
            self._audit(session, actor, "ACTIVATE_REQUESTED", document_id, version_id, None, {})
        return self.reindex(version_id, actor)

    def reindex(self, version_id: str, actor: str) -> KnowledgeIndexJobResponse:
        with self.database.session() as session:
            version = session.get(KnowledgeDocumentVersionModel, version_id)
            if not version: raise KeyError("knowledge version not found")
            job = KnowledgeIndexJobModel(job_id=str(uuid4()), document_version_id=version_id, operation="REINDEX", status="QUEUED", attempt_count=0, requested_by=actor, created_at_utc=_now()); session.add(job); self._audit(session, actor, "REINDEX_REQUESTED", version.document_id, version_id, job.job_id, {})
        self.run_job(job.job_id)
        with self.database.session() as session: return self._job(session.get(KnowledgeIndexJobModel, job.job_id))

    def jobs(self, limit: int, offset: int, status: str | None) -> KnowledgeIndexJobPage:
        with self.database.session() as session:
            q = select(KnowledgeIndexJobModel)
            if status: q = q.where(KnowledgeIndexJobModel.status == status)
            total = int(session.scalar(select(func.count()).select_from(q.subquery())) or 0); rows = list(session.scalars(q.order_by(KnowledgeIndexJobModel.created_at_utc.desc()).offset(offset).limit(limit)))
            return KnowledgeIndexJobPage(items=[self._job(x) for x in rows], total=total, limit=limit, offset=offset)

    def job(self, job_id: str) -> KnowledgeIndexJobResponse:
        with self.database.session() as session:
            row = session.get(KnowledgeIndexJobModel, job_id)
            if not row: raise KeyError("index job not found")
            return self._job(row)

    @staticmethod
    def _document(row: KnowledgeDocumentModel) -> KnowledgeDocumentResponse: return KnowledgeDocumentResponse(document_id=row.document_id, title=row.title, source_label=row.source_label, source_display=row.source_display or row.source_label, document_type=row.document_type, validity_status=row.validity_status, current_version=row.current_version, status=row.status, created_at_utc=row.created_at_utc, document_date=row.document_date, risk_tags=row.risk_tags or [], summary=row.summary)
    def _detail(self, session, document_id: str) -> KnowledgeDocumentDetailResponse:
        doc = session.get(KnowledgeDocumentModel, document_id)
        if not doc: raise KeyError("knowledge document not found")
        return KnowledgeDocumentDetailResponse(**self._document(doc).model_dump(), versions=[KnowledgeVersionResponse(document_version_id=x.document_version_id, version_no=x.version_no, status=x.status, parser_name=x.parser_name, page_count=x.page_count, indexed_at_utc=x.indexed_at_utc, failure_code=x.failure_code) for x in session.scalars(select(KnowledgeDocumentVersionModel).where(KnowledgeDocumentVersionModel.document_id == document_id).order_by(KnowledgeDocumentVersionModel.version_no.desc()))])
    @staticmethod
    def _job(row: KnowledgeIndexJobModel) -> KnowledgeIndexJobResponse: return KnowledgeIndexJobResponse(job_id=row.job_id, document_version_id=row.document_version_id, operation=row.operation, status=row.status, attempt_count=row.attempt_count, started_at_utc=row.started_at_utc, finished_at_utc=row.finished_at_utc, error_code=row.error_code)
    def _job_for_version(self, session, version_id: str) -> KnowledgeIndexJobResponse:
        return self._job(session.scalar(select(KnowledgeIndexJobModel).where(KnowledgeIndexJobModel.document_version_id == version_id).order_by(KnowledgeIndexJobModel.created_at_utc.desc())))
    @staticmethod
    def _audit(session, actor, action, document_id, version_id, job_id, detail): session.add(KnowledgeAuditModel(audit_id=str(uuid4()), actor=actor, action=action, document_id=document_id, document_version_id=version_id, job_id=job_id, detail_safe_json=detail, created_at_utc=_now()))
