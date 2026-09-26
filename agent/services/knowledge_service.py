from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from sqlalchemy import func, select

from agent.contracts.chat import KnowledgeCitation
from agent.contracts.knowledge import (
    KnowledgeDocumentDetailResponse, KnowledgeDocumentPage, KnowledgeDocumentResponse,
    KnowledgeIndexJobPage, KnowledgeIndexJobResponse, KnowledgeVersionResponse,
)
from agent.db.base import Database
from agent.db.models import KnowledgeAuditModel, KnowledgeDocumentModel, KnowledgeDocumentVersionModel, KnowledgeIndexJobModel
from agent.rag.chroma_adapter import ChromaKnowledgeRetriever


def _now() -> datetime:
    return datetime.now(timezone.utc)


class KnowledgeService:
    def __init__(self, database: Database, retriever: ChromaKnowledgeRetriever | None, document_directory: str, max_upload_bytes: int, allowed_extensions: str, chunk_size: int, chunk_overlap: int, top_k_max: int) -> None:
        self.database, self.retriever = database, retriever
        self.root = Path(document_directory)
        self.max_upload_bytes = max_upload_bytes
        self.allowed = {value.strip().lower() for value in allowed_extensions.split(",")}
        self.chunk_size, self.chunk_overlap, self.top_k_max = chunk_size, chunk_overlap, top_k_max

    def upload(self, *, filename: str, content: bytes, title: str, source_label: str, actor: str, document_id: str | None = None, expected_current_version: int | None = None) -> tuple[KnowledgeDocumentDetailResponse, KnowledgeIndexJobResponse, bool]:
        suffix = Path(filename).suffix.lower()
        if suffix not in self.allowed or not content or len(content) > self.max_upload_bytes:
            raise ValueError("unsupported or oversized knowledge document")
        checksum = hashlib.sha256(content).hexdigest()
        with self.database.session() as session:
            existing = session.scalar(select(KnowledgeDocumentVersionModel).where(KnowledgeDocumentVersionModel.checksum_sha256 == checksum))
            if existing:
                return self._detail(session, existing.document_id), self._job_for_version(session, existing.document_version_id), True
            now = _now()
            if document_id:
                document = session.get(KnowledgeDocumentModel, document_id)
                if not document:
                    raise KeyError("knowledge document not found")
                if expected_current_version is not None and document.current_version != expected_current_version:
                    raise RuntimeError("document version conflict")
                version_no = document.current_version + 1
            else:
                document_id, version_no = str(uuid4()), 1
                document = KnowledgeDocumentModel(document_id=document_id, title=title, source_label=source_label, checksum_sha256=checksum, current_version=version_no, status="UPLOADED", created_at_utc=now, created_by=actor)
                session.add(document)
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
            return self._detail(session, document_id), self._job(session.get(KnowledgeIndexJobModel, job.job_id)), False

    def run_job(self, job_id: str) -> None:
        if not self.retriever:
            raise RuntimeError("RAG is disabled")
        with self.database.session() as session:
            job = session.get(KnowledgeIndexJobModel, job_id)
            if not job: raise KeyError("index job not found")
            version = session.get(KnowledgeDocumentVersionModel, job.document_version_id)
            document = session.get(KnowledgeDocumentModel, version.document_id)
            job.status, job.attempt_count, job.started_at_utc = "RUNNING", job.attempt_count + 1, _now()
            version.status = "PARSING"
            try:
                text, page_count, parser = _extract_text(self.root / version.storage_key)
                chunks = _chunks(text, self.chunk_size, self.chunk_overlap)
                if not chunks: raise ValueError("document contains no indexable text")
                version.status = "INDEXING"
                records = [{"chunk_id": str(uuid4()), "text": body, "metadata": {"document_id": document.document_id, "document_version_id": version.document_version_id, "version_no": version.version_no, "title": document.title, "status": "ACTIVE", "page_or_section": f"段落 {index + 1}", "checksum_sha256": version.checksum_sha256}} for index, body in enumerate(chunks)]
                self.retriever.replace_version(version.document_version_id, records)
                # Only one version is searchable per document.
                for old in session.scalars(select(KnowledgeDocumentVersionModel).where(KnowledgeDocumentVersionModel.document_id == document.document_id, KnowledgeDocumentVersionModel.document_version_id != version.document_version_id, KnowledgeDocumentVersionModel.status == "ACTIVE")):
                    old.status, old.retired_at_utc = "RETIRED", _now(); self.retriever.delete_version(old.document_version_id)
                version.status, version.parser_name, version.page_count, version.indexed_at_utc = "ACTIVE", parser, page_count, _now()
                document.status = "ACTIVE"
                job.status, job.finished_at_utc = "SUCCEEDED", _now()
                self._audit(session, job.requested_by, "INDEX_SUCCEEDED", document.document_id, version.document_version_id, job.job_id, {"chunk_count": len(records)})
            except Exception as exc:
                version.status, version.failure_code, version.failure_detail_safe = "FAILED", "INDEX_FAILED", str(exc)[:512]
                job.status, job.error_code, job.error_detail_safe, job.finished_at_utc = "FAILED", "INDEX_FAILED", str(exc)[:512], _now()

    def search(self, query: str, top_k: int) -> tuple[list[dict[str, str]], list[KnowledgeCitation]]:
        if not self.retriever: raise RuntimeError("RAG is disabled")
        if not query.strip() or not 1 <= top_k <= self.top_k_max: raise ValueError("invalid knowledge query")
        chunks = self.retriever.search(query.strip(), top_k)
        with self.database.session() as session:
            active = {(row.document_id, row.document_version_id) for row in session.execute(select(KnowledgeDocumentVersionModel.document_id, KnowledgeDocumentVersionModel.document_version_id).where(KnowledgeDocumentVersionModel.status == "ACTIVE"))}
        chunks = [chunk for chunk in chunks if (chunk.document_id, chunk.document_version_id) in active]
        citations = [KnowledgeCitation(document_id=c.document_id, version_no=c.version_no, title=c.title, page_or_section=c.page_or_section, chunk_id=c.chunk_id, relevance_score=c.relevance_score) for c in chunks]
        return ([{"content": c.text, "title": c.title, "page_or_section": c.page_or_section} for c in chunks], citations)

    def list_documents(self, limit: int, offset: int, status: str | None) -> KnowledgeDocumentPage:
        with self.database.session() as session:
            q = select(KnowledgeDocumentModel)
            if status: q = q.where(KnowledgeDocumentModel.status == status)
            total = int(session.scalar(select(func.count()).select_from(q.subquery())) or 0)
            items = list(session.scalars(q.order_by(KnowledgeDocumentModel.created_at_utc.desc()).offset(offset).limit(limit)))
            return KnowledgeDocumentPage(items=[self._document(x) for x in items], total=total, limit=limit, offset=offset)

    def detail(self, document_id: str) -> KnowledgeDocumentDetailResponse:
        with self.database.session() as session: return self._detail(session, document_id)

    def retire(self, document_id: str, actor: str) -> None:
        with self.database.session() as session:
            doc = session.get(KnowledgeDocumentModel, document_id)
            if not doc: raise KeyError("knowledge document not found")
            for version in session.scalars(select(KnowledgeDocumentVersionModel).where(KnowledgeDocumentVersionModel.document_id == document_id, KnowledgeDocumentVersionModel.status == "ACTIVE")):
                version.status, version.retired_at_utc = "RETIRED", _now()
                if self.retriever: self.retriever.delete_version(version.document_version_id)
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
    def _document(row: KnowledgeDocumentModel) -> KnowledgeDocumentResponse: return KnowledgeDocumentResponse(document_id=row.document_id, title=row.title, source_label=row.source_label, current_version=row.current_version, status=row.status, created_at_utc=row.created_at_utc)
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


def _extract_text(path: Path) -> tuple[str, int | None, str]:
    suffix = path.suffix.lower()
    if suffix in {".txt", ".md"}: return path.read_text(encoding="utf-8"), None, "plain_text"
    if suffix == ".pdf":
        from pypdf import PdfReader
        pages = PdfReader(str(path)).pages; return "\n".join(page.extract_text() or "" for page in pages), len(pages), "pypdf"
    if suffix == ".docx":
        from docx import Document
        return "\n".join(p.text for p in Document(str(path)).paragraphs), None, "python-docx"
    raise ValueError("unsupported knowledge document")


def _chunks(text: str, size: int, overlap: int) -> list[str]:
    text, out, start = " ".join(text.split()), [], 0
    while start < len(text):
        end = min(len(text), start + size); out.append(text[start:end])
        if end == len(text): break
        start = end - overlap
    return out
