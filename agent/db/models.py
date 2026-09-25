from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, Integer, JSON, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    pass


class ViolationEventModel(Base):
    __tablename__ = "violation_events"

    event_uuid: Mapped[str] = mapped_column(String(36), primary_key=True)
    schema_version: Mapped[str] = mapped_column(String(16), nullable=False)
    camera_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    monitor_session_id: Mapped[str] = mapped_column(String(128), nullable=False)
    track_id: Mapped[int] = mapped_column(Integer, nullable=False)
    violation_type: Mapped[str] = mapped_column(String(64), index=True, nullable=False)
    severity: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    status: Mapped[str] = mapped_column(String(32), index=True, nullable=False)
    zone_id: Mapped[str | None] = mapped_column(String(128))
    zone_name: Mapped[str | None] = mapped_column(String(255))
    occurred_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True, nullable=False)
    resolved_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    snapshot_uri: Mapped[str | None] = mapped_column(String(1024))
    model_name: Mapped[str | None] = mapped_column(String(128))
    model_version: Mapped[str | None] = mapped_column(String(128))
    extra_details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class CameraStatusModel(Base):
    __tablename__ = "camera_statuses"

    camera_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    monitor_session_id: Mapped[str] = mapped_column(String(128), nullable=False)
    is_online: Mapped[bool] = mapped_column(Boolean, nullable=False)
    fps: Mapped[float] = mapped_column(Float, nullable=False)
    processed_frame_id: Mapped[int] = mapped_column(Integer, nullable=False)
    active_workers_count: Mapped[int] = mapped_column(Integer, nullable=False)
    model_name: Mapped[str | None] = mapped_column(String(128))
    model_version: Mapped[str | None] = mapped_column(String(128))
    reported_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    extra_details: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)


class CameraConfigModel(Base):
    __tablename__ = "camera_configs"

    camera_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    config_version: Mapped[int] = mapped_column(Integer, nullable=False)
    source_width: Mapped[int] = mapped_column(Integer, nullable=False)
    source_height: Mapped[int] = mapped_column(Integer, nullable=False)
    enter_debounce_frames: Mapped[int] = mapped_column(Integer, nullable=False)
    exit_debounce_frames: Mapped[int] = mapped_column(Integer, nullable=False)
    helmet_debounce_frames: Mapped[int] = mapped_column(Integer, nullable=False)
    alarm_dwell_threshold_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    zones: Mapped[list[dict[str, Any]]] = mapped_column(JSON, nullable=False, default=list)
    updated_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
