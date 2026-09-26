from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import AnyHttpUrl, BaseModel, Field, field_validator, model_validator


SourceType = Literal["rtsp", "file"]
DesiredState = Literal["RUNNING", "STOPPED"]


class CvNodeCreateRequest(BaseModel):
    node_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
    display_name: str = Field(min_length=1, max_length=255)
    control_url: AnyHttpUrl
    capacity: int = Field(default=1, ge=1, le=128)
    control_token: str | None = Field(default=None, min_length=24, max_length=256, repr=False)


class CvNodeResponse(BaseModel):
    node_id: str
    display_name: str
    control_url: str
    is_online: bool
    active_sessions: int
    capacity: int
    last_heartbeat_at_utc: datetime | None = None


class CvNodeEnrollmentResponse(CvNodeResponse):
    control_token: str


class CvNodeHeartbeatRequest(BaseModel):
    active_sessions: int = Field(default=0, ge=0)
    capacity: int = Field(default=1, ge=1, le=128)


class ManagedCameraCreateRequest(BaseModel):
    camera_id: str = Field(min_length=1, max_length=128, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
    display_name: str = Field(min_length=1, max_length=255)
    node_id: str = Field(min_length=1, max_length=128)
    source_type: SourceType
    source_uri: str = Field(min_length=1, max_length=1024)

    @field_validator("source_uri")
    @classmethod
    def supported_source(cls, value: str) -> str:
        value = value.strip()
        if value.startswith(("rtsp://", "rtsps://")) or not ("://" in value):
            return value
        raise ValueError("source_uri must be an rtsp/rtsps URL or a CV-node local file path")

    @model_validator(mode="after")
    def source_matches_type(self) -> "ManagedCameraCreateRequest":
        if self.source_type == "rtsp" and not self.source_uri.startswith(("rtsp://", "rtsps://")):
            raise ValueError("rtsp source_type requires an rtsp/rtsps URL")
        if self.source_type == "file" and "://" in self.source_uri:
            raise ValueError("file source_type requires a CV-node local file path")
        return self


class ManagedCameraSourceUpdate(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=255)
    node_id: str = Field(min_length=1, max_length=128)
    source_type: SourceType
    # Omit this field for a display-name-only update.  The stored source is
    # deliberately never returned to Web, so a UI cannot prefill it.
    source_uri: str | None = Field(default=None, min_length=1, max_length=1024)

    @model_validator(mode="after")
    def source_matches_type(self) -> "ManagedCameraSourceUpdate":
        if self.source_uri is None:
            return self
        if self.source_type == "rtsp" and not self.source_uri.startswith(("rtsp://", "rtsps://")):
            raise ValueError("rtsp source_type requires an rtsp/rtsps URL")
        if self.source_type == "file" and "://" in self.source_uri:
            raise ValueError("file source_type requires a CV-node local file path")
        return self


class CvNodeMediaEntry(BaseModel):
    name: str
    path: str


class CvNodeMediaDirectoryResponse(BaseModel):
    current_path: str
    parent_path: str | None = None
    directories: list[CvNodeMediaEntry]
    files: list[CvNodeMediaEntry]


class ManagedCameraResponse(BaseModel):
    camera_id: str
    display_name: str
    node_id: str
    source_type: SourceType
    source_uri_masked: str
    desired_state: DesiredState
    monitor_session_id: str | None = None


class MonitoringSessionResponse(BaseModel):
    camera_id: str
    node_id: str
    monitor_session_id: str | None = None
    desired_state: DesiredState
    accepted: bool
