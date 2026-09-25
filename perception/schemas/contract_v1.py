from __future__ import annotations

import time
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from perception.schemas.detection import ViolationEvent


class TimeAnchor:
    """
    Precision time anchor tying session start monotonic clock to wall-clock UTC.
    Calculates UTC timestamps strictly by monotonic offset:
      occurred_at_utc = session_started_at_utc + (event_monotonic - session_started_monotonic)
    """

    def __init__(
        self,
        session_started_at_utc: Optional[Union[datetime, str]] = None,
        session_started_monotonic: Optional[float] = None,
    ):
        if session_started_at_utc is not None:
            if isinstance(session_started_at_utc, str):
                dt = datetime.fromisoformat(session_started_at_utc.replace("Z", "+00:00"))
                self.session_started_at_utc = dt.astimezone(timezone.utc)
            elif session_started_at_utc.tzinfo is None:
                self.session_started_at_utc = session_started_at_utc.replace(tzinfo=timezone.utc)
            else:
                self.session_started_at_utc = session_started_at_utc.astimezone(timezone.utc)
        else:
            self.session_started_at_utc = datetime.now(timezone.utc)

        self.session_started_monotonic = (
            session_started_monotonic
            if session_started_monotonic is not None
            else time.monotonic()
        )

    def to_utc(self, monotonic_seconds: float) -> datetime:
        delta = monotonic_seconds - self.session_started_monotonic
        return self.session_started_at_utc + timedelta(seconds=delta)

    def to_utc_iso(self, monotonic_seconds: Optional[float]) -> Optional[str]:
        if monotonic_seconds is None:
            return None
        dt = self.to_utc(monotonic_seconds)
        # Format as strict ISO 8601 with Z suffix
        return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class PerceptionEventContractV1(BaseModel):
    """
    Standardized Violation Event Contract v1 for inter-system integration with Agent/Web.
    """
    schema_version: str = Field("1.0", description="Contract schema version")
    event_uuid: str = Field(..., description="Unique event UUID; invariant across entire lifecycle")
    event_action: str = Field("UPSERT", description="Event operation action, defaults to UPSERT")
    camera_id: str = Field(..., description="Camera identifier")
    monitor_session_id: str = Field(..., description="Session identifier for the continuous monitoring run")
    track_id: int = Field(..., description="Temporary track identifier within session")
    violation_type: str = Field(..., description="Violation category, e.g. DANGER_ZONE_INTRUSION, NO_HELMET")
    severity: str = Field(..., description="Alert level: INFO, WARNING, CRITICAL")
    status: str = Field("ACTIVE", description="Lifecycle status: ACTIVE, RESOLVED, FALSE_ALARM")
    zone_id: Optional[str] = Field(None, description="Unique zone identifier in database")
    zone_name: Optional[str] = Field(None, description="Human-readable zone display name")
    occurred_at_utc: str = Field(..., description="UTC ISO 8601 timestamp of violation onset")
    resolved_at_utc: Optional[str] = Field(None, description="UTC ISO 8601 timestamp of violation resolution")
    duration_seconds: float = Field(0.0, ge=0.0, description="Elapsed violation duration in seconds")
    snapshot_uri: Optional[str] = Field(None, description="Relative media storage URI, e.g., snapshots/20260925/uuid.jpg")
    model_name: str = Field("helmet_head_person_m", description="Active detector model name")
    model_version: str = Field("legacy-yolov5", description="Detector version / framework")
    extra_details: Dict[str, Any] = Field(default_factory=dict, description="Metadata details (bbox, feet, escalation)")


class AgentEventResponseV1(BaseModel):
    """
    Standardized response from Agent POST /internal/v1/perception/events.
    """
    event_uuid: str
    operation: str = Field(..., description="CREATED or UPDATED")
    status: str
    server_received_at_utc: str


class CameraStatusContractV1(BaseModel):
    """
    Payload for PUT /internal/v1/perception/cameras/{camera_id}/status.
    """
    camera_id: str
    is_online: bool = True
    fps: float = 0.0
    active_workers_count: int = 0
    helmet_compliance_rate: float = 1.0
    model_name: Optional[str] = None
    model_version: Optional[str] = None
    reported_at_utc: str = Field(
        default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    )


class CameraZoneConfig(BaseModel):
    zone_id: str
    zone_name: str
    polygon: List[List[float]]
    enabled: bool = True
    alarm_dwell_threshold_seconds: float = 5.0


class CameraRunConfigContractV1(BaseModel):
    """
    Payload from GET /internal/v1/perception/cameras/{camera_id}/config.
    """
    camera_id: str
    config_version: int = 1
    source_resolution: Dict[str, int] = Field(default_factory=lambda: {"width": 1920, "height": 1080})
    enter_debounce_frames: int = 3
    exit_debounce_frames: int = 5
    helmet_debounce_frames: int = 5
    alarm_dwell_threshold_seconds: float = 5.0
    zones: List[CameraZoneConfig] = Field(default_factory=list)


def to_event_contract_v1(
    event: ViolationEvent,
    time_anchor: TimeAnchor,
    monitor_session_id: str,
    zone_id: Optional[str] = None,
    relative_snapshot_uri: Optional[str] = None,
    model_name: str = "helmet_head_person_m",
    model_version: str = "legacy-yolov5",
    extra_details: Optional[Dict[str, Any]] = None,
) -> PerceptionEventContractV1:
    """
    Converts internal ViolationEvent into PerceptionEventContractV1.
    """
    occurred_iso = time_anchor.to_utc_iso(event.start_time)
    resolved_iso = time_anchor.to_utc_iso(event.end_time) if event.end_time is not None else None

    # Merge extra details
    merged_details = dict(event.extra_details)
    if extra_details:
        merged_details.update(extra_details)

    status = "RESOLVED" if event.end_time is not None else event.status

    return PerceptionEventContractV1(
        schema_version="1.0",
        event_uuid=event.event_uuid,
        event_action="UPSERT",
        camera_id=event.camera_id,
        monitor_session_id=monitor_session_id,
        track_id=event.track_id,
        violation_type=str(event.violation_type.value if hasattr(event.violation_type, "value") else event.violation_type),
        severity=str(event.severity.value if hasattr(event.severity, "value") else event.severity),
        status=status,
        zone_id=zone_id,
        zone_name=event.zone_name,
        occurred_at_utc=occurred_iso,
        resolved_at_utc=resolved_iso,
        duration_seconds=round(event.duration_seconds, 2),
        snapshot_uri=relative_snapshot_uri,
        model_name=model_name,
        model_version=model_version,
        extra_details=merged_details,
    )
