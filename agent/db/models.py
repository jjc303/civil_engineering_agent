from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, func
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


class CvNodeModel(Base):
    __tablename__ = "cv_nodes"

    node_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    control_url: Mapped[str] = mapped_column(String(1024), nullable=False)
    control_token_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    is_online: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    active_sessions: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_heartbeat_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class ManagedCameraModel(Base):
    __tablename__ = "managed_cameras"

    camera_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    node_id: Mapped[str] = mapped_column(String(128), index=True, nullable=False)
    source_type: Mapped[str] = mapped_column(String(16), nullable=False)
    source_uri_encrypted: Mapped[str] = mapped_column(Text, nullable=False)
    source_uri_masked: Mapped[str] = mapped_column(String(1024), nullable=False)
    desired_state: Mapped[str] = mapped_column(String(16), nullable=False, default="STOPPED")
    monitor_session_id: Mapped[str | None] = mapped_column(String(128))
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())


class ConversationSessionModel(Base):
    __tablename__ = "conversation_sessions"
    conversation_id: Mapped[str] = mapped_column(String(128), primary_key=True)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_active_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    expires_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class ConversationTurnModel(Base):
    __tablename__ = "conversation_turns"
    __table_args__ = (UniqueConstraint("conversation_id", "sequence_no", name="uq_conversation_turn_sequence"),)
    turn_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversation_sessions.conversation_id", ondelete="CASCADE"), nullable=False, index=True)
    sequence_no: Mapped[int] = mapped_column(Integer, nullable=False)
    user_text: Mapped[str] = mapped_column(Text, nullable=False)
    assistant_text: Mapped[str] = mapped_column(Text, nullable=False)
    verified_facts_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ConversationSummaryModel(Base):
    __tablename__ = "conversation_summaries"
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversation_sessions.conversation_id", ondelete="CASCADE"), primary_key=True)
    summary_text: Mapped[str] = mapped_column(Text, nullable=False)
    covered_through_seq: Mapped[int] = mapped_column(Integer, nullable=False)
    updated_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class ConversationToolAuditModel(Base):
    __tablename__ = "conversation_tool_audits"
    audit_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    conversation_id: Mapped[str] = mapped_column(ForeignKey("conversation_sessions.conversation_id", ondelete="CASCADE"), nullable=False, index=True)
    turn_id: Mapped[str | None] = mapped_column(ForeignKey("conversation_turns.turn_id", ondelete="SET NULL"))
    tool_name: Mapped[str] = mapped_column(String(64), nullable=False)
    success: Mapped[bool] = mapped_column(Boolean, nullable=False)
    duration_ms: Mapped[int] = mapped_column(Integer, nullable=False)
    purpose: Mapped[str] = mapped_column(String(256), nullable=False)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class KnowledgeDocumentModel(Base):
    __tablename__ = "knowledge_documents"
    document_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    source_label: Mapped[str] = mapped_column(String(512), nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    current_version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)
    retired_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class KnowledgeDocumentVersionModel(Base):
    __tablename__ = "knowledge_document_versions"
    __table_args__ = (UniqueConstraint("document_id", "version_no", name="uq_knowledge_document_version"),)
    document_version_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_id: Mapped[str] = mapped_column(ForeignKey("knowledge_documents.document_id"), nullable=False, index=True)
    version_no: Mapped[int] = mapped_column(Integer, nullable=False)
    storage_key: Mapped[str] = mapped_column(String(1024), nullable=False)
    checksum_sha256: Mapped[str] = mapped_column(String(64), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    parser_name: Mapped[str | None] = mapped_column(String(128))
    page_count: Mapped[int | None] = mapped_column(Integer)
    indexed_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    retired_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_code: Mapped[str | None] = mapped_column(String(64))
    failure_detail_safe: Mapped[str | None] = mapped_column(String(512))
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_by: Mapped[str] = mapped_column(String(128), nullable=False)


class KnowledgeIndexJobModel(Base):
    __tablename__ = "knowledge_index_jobs"
    job_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    document_version_id: Mapped[str] = mapped_column(ForeignKey("knowledge_document_versions.document_version_id"), nullable=False, index=True)
    operation: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    started_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at_utc: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(64))
    error_detail_safe: Mapped[str | None] = mapped_column(String(512))
    requested_by: Mapped[str] = mapped_column(String(128), nullable=False)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class KnowledgeAuditModel(Base):
    __tablename__ = "knowledge_audits"
    audit_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    action: Mapped[str] = mapped_column(String(64), nullable=False)
    document_id: Mapped[str | None] = mapped_column(String(36), index=True)
    document_version_id: Mapped[str | None] = mapped_column(String(36))
    job_id: Mapped[str | None] = mapped_column(String(36))
    detail_safe_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class AssistantUiConfigModel(Base):
    __tablename__ = "assistant_ui_configs"
    config_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    assistant_name: Mapped[str] = mapped_column(String(128), nullable=False)
    welcome_message: Mapped[str] = mapped_column(Text, nullable=False)
    input_placeholder: Mapped[str] = mapped_column(String(512), nullable=False)
    quick_questions: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    show_evidence: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    updated_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_by: Mapped[str] = mapped_column(String(128), nullable=False)


class AssistantUiConfigAuditModel(Base):
    __tablename__ = "assistant_ui_config_audits"
    audit_id: Mapped[str] = mapped_column(String(36), primary_key=True)
    config_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    actor: Mapped[str] = mapped_column(String(128), nullable=False)
    detail_safe_json: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False, default=dict)
    created_at_utc: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
