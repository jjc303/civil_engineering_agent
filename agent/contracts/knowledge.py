from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field
from typing import Literal

DocumentType = Literal["STANDARD", "ACCIDENT_REPORT"]
StandardValidity = Literal["CURRENT", "SUPERSEDED", "UNKNOWN"]


class StandardValidityUpdate(BaseModel):
    validity_status: StandardValidity


class KnowledgeMetadataUpdate(BaseModel):
    document_date: datetime | None = None
    risk_tags: list[str] = Field(default_factory=list)
    summary: str | None = None
    source_display: str | None = None


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
    source_display: str
    document_type: DocumentType
    validity_status: StandardValidity
    current_version: int
    status: str
    created_at_utc: datetime
    document_date: datetime | None = None
    risk_tags: list[str] = Field(default_factory=list)
    summary: str | None = None


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
