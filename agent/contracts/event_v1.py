from __future__ import annotations

from datetime import datetime
from enum import Enum
from pathlib import PurePosixPath
from typing import Any
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator


class ViolationType(str, Enum):
    NO_HELMET = "NO_HELMET"
    DANGER_ZONE_INTRUSION = "DANGER_ZONE_INTRUSION"
    DWELL_TIMEOUT = "DWELL_TIMEOUT"


class ViolationSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class EventStatus(str, Enum):
    ACTIVE = "ACTIVE"
    RESOLVED = "RESOLVED"
    FALSE_ALARM = "FALSE_ALARM"


class SafetyViolationEventV1(BaseModel):
    schema_version: str = Field(default="1.0", pattern=r"^1\.0$")
    event_uuid: UUID
    event_action: str = Field(default="UPSERT", pattern=r"^UPSERT$")
    camera_id: str = Field(min_length=1, max_length=128)
    monitor_session_id: str = Field(min_length=1, max_length=128)
    track_id: int = Field(ge=0)
    violation_type: ViolationType
    severity: ViolationSeverity
    status: EventStatus
    zone_id: str | None = Field(default=None, max_length=128)
    zone_name: str | None = Field(default=None, max_length=255)
    occurred_at_utc: datetime
    resolved_at_utc: datetime | None = None
    duration_seconds: float = Field(ge=0)
    snapshot_uri: str | None = Field(default=None, max_length=1024)
    model_name: str | None = Field(default=None, max_length=128)
    model_version: str | None = Field(default=None, max_length=128)
    extra_details: dict[str, Any] = Field(default_factory=dict)

    @field_validator("snapshot_uri")
    @classmethod
    def snapshot_must_be_relative(cls, value: str | None) -> str | None:
        if value is None:
            return value
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError("snapshot_uri must be a relative media URI")
        return value

    @model_validator(mode="after")
    def validate_resolution_time(self) -> "SafetyViolationEventV1":
        if self.status == EventStatus.RESOLVED and self.resolved_at_utc is None:
            raise ValueError("resolved_at_utc is required for RESOLVED events")
        if self.resolved_at_utc and self.resolved_at_utc < self.occurred_at_utc:
            raise ValueError("resolved_at_utc must not precede occurred_at_utc")
        return self


class CameraStatusReportV1(BaseModel):
    camera_id: str = Field(min_length=1, max_length=128)
    monitor_session_id: str = Field(min_length=1, max_length=128)
    is_online: bool
    fps: float = Field(ge=0)
    processed_frame_id: int = Field(ge=0)
    active_workers_count: int = Field(ge=0)
    model_name: str | None = Field(default=None, max_length=128)
    model_version: str | None = Field(default=None, max_length=128)
    reported_at_utc: datetime
    extra_details: dict[str, Any] = Field(default_factory=dict)


class EventUpsertResponse(BaseModel):
    event_uuid: UUID
    operation: str
    status: EventStatus
    server_received_at_utc: datetime
