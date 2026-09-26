from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class KnowledgeCitationResponse(BaseModel):
    document_id: str
    version_no: int
    title: str
    page_or_section: str
    chunk_id: str
    relevance_score: float


class KnowledgeDocumentResponse(BaseModel):
    document_id: str
    title: str
    source_label: str
    current_version: int
    status: str
    created_at_utc: datetime


class KnowledgeVersionResponse(BaseModel):
    document_version_id: str
    version_no: int
    status: str
    parser_name: str | None = None
    page_count: int | None = None
    indexed_at_utc: datetime | None = None
    failure_code: str | None = None


class KnowledgeDocumentDetailResponse(KnowledgeDocumentResponse):
    versions: list[KnowledgeVersionResponse]


class KnowledgeDocumentPage(BaseModel):
    items: list[KnowledgeDocumentResponse]
    total: int
    limit: int
    offset: int


class KnowledgeIndexJobResponse(BaseModel):
    job_id: str
    document_version_id: str
    operation: str
    status: str
    attempt_count: int
    started_at_utc: datetime | None = None
    finished_at_utc: datetime | None = None
    error_code: str | None = None


class KnowledgeIndexJobPage(BaseModel):
    items: list[KnowledgeIndexJobResponse]
    total: int
    limit: int
    offset: int
