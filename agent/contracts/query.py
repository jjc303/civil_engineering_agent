from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

from .event_v1 import EventStatus, ViolationSeverity, ViolationType


class ViolationQuery(BaseModel):
    camera_id: str | None = None
    violation_type: ViolationType | None = None
    severity: ViolationSeverity | None = None
    status: EventStatus | None = None
    start_time_utc: datetime | None = None
    end_time_utc: datetime | None = None
    limit: int = Field(default=100, ge=1, le=500)
    offset: int = Field(default=0, ge=0)


class ViolationRecord(BaseModel):
    event_uuid: str
    camera_id: str
    monitor_session_id: str
    track_id: int
    violation_type: ViolationType
    severity: ViolationSeverity
    status: EventStatus
    zone_id: str | None
    zone_name: str | None
    occurred_at_utc: datetime
    resolved_at_utc: datetime | None
    duration_seconds: float
    snapshot_uri: str | None
    model_name: str | None

    @field_validator("occurred_at_utc", "resolved_at_utc", mode="after")
    @classmethod
    def normalize_utc(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
    model_version: str | None
    extra_details: dict[str, Any]


class ViolationStatisticsResponse(BaseModel):
    total_violations: int
    average_duration_seconds: float
    by_type: dict[str, int]
    by_severity: dict[str, int]


class ViolationPageResponse(BaseModel):
    items: list[ViolationRecord]
    total: int = Field(ge=0)
    limit: int = Field(ge=1)
    offset: int = Field(ge=0)


class CameraStatusResponse(BaseModel):
    camera_id: str
    monitor_session_id: str
    is_online: bool
    fps: float
    processed_frame_id: int
    active_workers_count: int
    model_name: str | None
    model_version: str | None
    reported_at_utc: datetime
    extra_details: dict[str, Any]


class SafetyQueryRequest(BaseModel):
    operation: Literal["violations", "statistics", "camera_status"]
    query: ViolationQuery = Field(default_factory=ViolationQuery)
    camera_id: str | None = None


class SafetyQueryResponse(BaseModel):
    operation: str
    result: dict[str, Any]
    summary: str
