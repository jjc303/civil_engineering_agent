from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from agent.contracts.knowledge import (
    DocumentType,
    KnowledgeDocumentDetailResponse,
    KnowledgeDocumentResponse,
    KnowledgeIndexJobResponse,
    KnowledgeVersionResponse,
    StandardValidity,
)
from agent.db.models import (
    KnowledgeAuditModel,
    KnowledgeDocumentModel,
    KnowledgeDocumentVersionModel,
    KnowledgeIndexJobModel,
)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class KnowledgeRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def find_version_by_checksum(self, checksum: str) -> KnowledgeDocumentVersionModel | None:
        return self.session.scalar(
            select(KnowledgeDocumentVersionModel).where(KnowledgeDocumentVersionModel.checksum_sha256 == checksum)
        )

    def find_document_by_source_label(self, source_label: str) -> KnowledgeDocumentModel | None:
        return self.session.scalar(
            select(KnowledgeDocumentModel).where(KnowledgeDocumentModel.source_label == source_label)
        )

    def get_document(self, document_id: str) -> KnowledgeDocumentModel | None:
        return self.session.get(KnowledgeDocumentModel, document_id)

    def get_version(self, version_id: str) -> KnowledgeDocumentVersionModel | None:
        return self.session.get(KnowledgeDocumentVersionModel, version_id)

    def get_job(self, job_id: str) -> KnowledgeIndexJobModel | None:
        return self.session.get(KnowledgeIndexJobModel, job_id)

    def get_job_for_version(self, version_id: str) -> KnowledgeIndexJobResponse | None:
        row = self.session.scalar(
            select(KnowledgeIndexJobModel)
            .where(KnowledgeIndexJobModel.document_version_id == version_id)
            .order_by(KnowledgeIndexJobModel.created_at_utc.desc())
        )
        return self.to_job_response(row) if row else None

    def list_active_version_ids_by_types(self, missing_types: list[str]) -> list[str]:
        return list(
            self.session.scalars(
                select(KnowledgeDocumentVersionModel.document_version_id)
                .join(KnowledgeDocumentModel)
                .where(
                    KnowledgeDocumentVersionModel.status == "ACTIVE",
                    KnowledgeDocumentModel.document_type.in_(missing_types),
                )
            )
        )

    def list_unsummarized_active_document_ids(self) -> list[str]:
        return list(
            self.session.scalars(
                select(KnowledgeDocumentModel.document_id).where(
                    KnowledgeDocumentModel.status == "ACTIVE",
                    (KnowledgeDocumentModel.summary.is_(None)) | (KnowledgeDocumentModel.summary == ""),
                ).order_by(KnowledgeDocumentModel.created_at_utc)
            )
        )

    def list_documents(
        self, limit: int, offset: int, status: str | None, document_type: DocumentType | None = None
    ) -> tuple[list[KnowledgeDocumentResponse], int]:
        q = select(KnowledgeDocumentModel)
        if status:
            q = q.where(KnowledgeDocumentModel.status == status)
        if document_type:
            q = q.where(KnowledgeDocumentModel.document_type == document_type)
        total = int(self.session.scalar(select(func.count()).select_from(q.subquery())) or 0)
        items = list(
            self.session.scalars(
                q.order_by(KnowledgeDocumentModel.created_at_utc.desc()).offset(offset).limit(limit)
            )
        )
        return [self.to_document_response(x) for x in items], total

    def get_document_detail(self, document_id: str) -> KnowledgeDocumentDetailResponse | None:
        doc = self.session.get(KnowledgeDocumentModel, document_id)
        if not doc:
            return None
        versions = list(
            self.session.scalars(
                select(KnowledgeDocumentVersionModel)
                .where(KnowledgeDocumentVersionModel.document_id == document_id)
                .order_by(KnowledgeDocumentVersionModel.version_no.desc())
            )
        )
        return KnowledgeDocumentDetailResponse(
            **self.to_document_response(doc).model_dump(),
            versions=[
                KnowledgeVersionResponse(
                    document_version_id=x.document_version_id,
                    version_no=x.version_no,
                    status=x.status,
                    parser_name=x.parser_name,
                    page_count=x.page_count,
                    indexed_at_utc=x.indexed_at_utc,
                    failure_code=x.failure_code,
                )
                for x in versions
            ],
        )

    def list_jobs(
        self, limit: int, offset: int, status: str | None
    ) -> tuple[list[KnowledgeIndexJobResponse], int]:
        q = select(KnowledgeIndexJobModel)
        if status:
            q = q.where(KnowledgeIndexJobModel.status == status)
        total = int(self.session.scalar(select(func.count()).select_from(q.subquery())) or 0)
        rows = list(
            self.session.scalars(
                q.order_by(KnowledgeIndexJobModel.created_at_utc.desc()).offset(offset).limit(limit)
            )
        )
        return [self.to_job_response(x) for x in rows], total

    def get_active_versions_validity(self, document_type: DocumentType) -> dict[tuple[str, str], str]:
        query_active = select(
            KnowledgeDocumentVersionModel.document_id,
            KnowledgeDocumentVersionModel.document_version_id,
            KnowledgeDocumentModel.validity_status,
        ).join(KnowledgeDocumentModel).where(
            KnowledgeDocumentVersionModel.status == "ACTIVE",
            KnowledgeDocumentModel.document_type == document_type,
        )
        if document_type == "STANDARD":
            query_active = query_active.where(KnowledgeDocumentModel.validity_status != "SUPERSEDED")
        return {
            (row.document_id, row.document_version_id): row.validity_status
            for row in self.session.execute(query_active)
        }

    def get_standard_catalog_states(self) -> dict[str, tuple[str, StandardValidity]]:
        rows = self.session.execute(
            select(
                KnowledgeDocumentModel.source_label,
                KnowledgeDocumentModel.validity_status,
                KnowledgeDocumentVersionModel.status,
                KnowledgeDocumentVersionModel.failure_detail_safe,
            )
            .join(KnowledgeDocumentVersionModel)
            .where(
                KnowledgeDocumentModel.document_type == "STANDARD",
                KnowledgeDocumentVersionModel.version_no == KnowledgeDocumentModel.current_version,
            )
        )
        return {
            row.source_label: (
                (
                    "已索引"
                    if row.status == "ACTIVE"
                    else "需 OCR"
                    if row.status == "FAILED" and "no indexable text" in (row.failure_detail_safe or "")
                    else "索引失败"
                    if row.status == "FAILED"
                    else "待索引"
                ),
                row.validity_status,
            )
            for row in rows
        }

    def record_audit(
        self,
        actor: str,
        action: str,
        document_id: str | None = None,
        document_version_id: str | None = None,
        job_id: str | None = None,
        detail: dict[str, Any] | None = None,
    ) -> None:
        self.session.add(
            KnowledgeAuditModel(
                audit_id=str(uuid4()),
                actor=actor,
                action=action,
                document_id=document_id,
                document_version_id=document_version_id,
                job_id=job_id,
                detail_safe_json=detail or {},
                created_at_utc=_utc_now(),
            )
        )

    @staticmethod
    def to_document_response(row: KnowledgeDocumentModel) -> KnowledgeDocumentResponse:
        return KnowledgeDocumentResponse(
            document_id=row.document_id,
            title=row.title,
            source_label=row.source_label,
            source_display=row.source_display or row.source_label,
            document_type=row.document_type,
            validity_status=row.validity_status,
            current_version=row.current_version,
            status=row.status,
            created_at_utc=row.created_at_utc,
            document_date=row.document_date,
            risk_tags=row.risk_tags or [],
            summary=row.summary,
        )

    @staticmethod
    def to_job_response(row: KnowledgeIndexJobModel) -> KnowledgeIndexJobResponse:
        return KnowledgeIndexJobResponse(
            job_id=row.job_id,
            document_version_id=row.document_version_id,
            operation=row.operation,
            status=row.status,
            attempt_count=row.attempt_count,
            started_at_utc=row.started_at_utc,
            finished_at_utc=row.finished_at_utc,
            error_code=row.error_code,
        )
