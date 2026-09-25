from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, model_validator


class SourceResolution(BaseModel):
    width: int = Field(default=1920, ge=1)
    height: int = Field(default=1080, ge=1)


class DangerZoneConfigV1(BaseModel):
    zone_id: str = Field(min_length=1, max_length=128)
    zone_name: str = Field(min_length=1, max_length=255)
    polygon: list[list[float]] = Field(min_length=3, max_length=128)
    enabled: bool = True
    alarm_dwell_threshold_seconds: float = Field(default=5.0, gt=0, le=3600)

    @model_validator(mode="after")
    def polygon_points_must_have_xy(self) -> "DangerZoneConfigV1":
        if any(len(point) != 2 for point in self.polygon):
            raise ValueError("each polygon point must contain exactly [x, y]")
        return self


class CameraConfigUpdateRequest(BaseModel):
    """Web/Agent write request. The server owns monotonically increasing config_version."""

    expected_version: int | None = Field(default=None, ge=1)
    source_resolution: SourceResolution = Field(default_factory=SourceResolution)
    enter_debounce_frames: int = Field(default=3, ge=1, le=300)
    exit_debounce_frames: int = Field(default=5, ge=1, le=300)
    helmet_debounce_frames: int = Field(default=5, ge=1, le=300)
    alarm_dwell_threshold_seconds: float = Field(default=5.0, gt=0, le=3600)
    zones: list[DangerZoneConfigV1] = Field(default_factory=list)

    @model_validator(mode="after")
    def zone_ids_must_be_unique(self) -> "CameraConfigUpdateRequest":
        ids = [zone.zone_id for zone in self.zones]
        if len(ids) != len(set(ids)):
            raise ValueError("zone_id values must be unique per camera")
        return self


class CameraRunConfigV1(BaseModel):
    camera_id: str
    config_version: int = Field(ge=1)
    source_resolution: SourceResolution
    enter_debounce_frames: int
    exit_debounce_frames: int
    helmet_debounce_frames: int
    alarm_dwell_threshold_seconds: float
    zones: list[DangerZoneConfigV1]
