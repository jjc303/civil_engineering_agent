from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from .actions import PendingActionResponse
from .query import ViolationRecord


RectificationTaskStatus = Literal["PENDING", "IN_PROGRESS", "COMPLETED", "CANCELLED"]


class RectificationTaskRecord(BaseModel):
    task_id: str
    event_uuid: str
    title: str
    description: str | None = None
    owner: str
    due_at_utc: datetime
    status: RectificationTaskStatus
    completed_at_utc: datetime | None = None
    created_at_utc: datetime
    updated_at_utc: datetime
    camera_id: str
    violation_type: str
    severity: str
    violation_status: str
    occurred_at_utc: datetime
    snapshot_uri: str | None = None

    @field_validator("due_at_utc", "completed_at_utc", "created_at_utc", "updated_at_utc", "occurred_at_utc", mode="after")
    @classmethod
    def normalize_utc(cls, value: datetime | None) -> datetime | None:
        if value is None:
            return None
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class RectificationTaskAudit(BaseModel):
    audit_id: str
    task_id: str
    action: str
    actor: str
    detail_safe_json: dict[str, object] = Field(default_factory=dict)
    created_at_utc: datetime

    @field_validator("created_at_utc", mode="after")
    @classmethod
    def normalize_utc(cls, value: datetime) -> datetime:
        return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class RectificationTaskPageResponse(BaseModel):
    items: list[RectificationTaskRecord]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)


class RectificationTaskDetail(BaseModel):
    task: RectificationTaskRecord
    violation: ViolationRecord
    audits: list[RectificationTaskAudit]


class RectificationTaskCreateRequest(BaseModel):
    conversation_id: str = Field(min_length=1, max_length=128)
    event_uuid: str = Field(min_length=36, max_length=36)
    title: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=4000)
    owner: str = Field(min_length=1, max_length=128)
    due_at_utc: datetime


class RectificationTaskUpdateRequest(BaseModel):
    conversation_id: str = Field(min_length=1, max_length=128)
    owner: str | None = Field(default=None, min_length=1, max_length=128)
    due_at_utc: datetime | None = None
    status: RectificationTaskStatus | None = None
    note: str | None = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def require_change(self) -> "RectificationTaskUpdateRequest":
        if not any((self.owner, self.due_at_utc, self.status, self.note)):
            raise ValueError("at least one task update is required")
        return self


class RectificationPendingActionResponse(BaseModel):
    pending_action: PendingActionResponse
