from __future__ import annotations

import time
import uuid
from enum import Enum
from typing import Dict, List, Optional, Tuple

from perception.geometry.danger_zone import person_in_danger_zone
from perception.schemas.detection import (
    DangerZone,
    TrackedPerson,
    ViolationEvent,
    ViolationSeverity,
    ViolationType,
)


class ZoneIntrusionState(str, Enum):
    OUTSIDE = "OUTSIDE"
    PENDING_ENTER = "PENDING_ENTER"
    INTRUSION = "INTRUSION"
    DWELL_TIMEOUT = "DWELL_TIMEOUT"
    PENDING_EXIT = "PENDING_EXIT"


class PersonZoneTracker:
    """Tracks danger zone intrusion state and dwell time for a specific worker in a specific zone."""

    def __init__(self, track_id: int, zone_name: str, dwell_threshold: float = 5.0):
        self.track_id = track_id
        self.zone_name = zone_name
        self.dwell_threshold = dwell_threshold

        self.state: ZoneIntrusionState = ZoneIntrusionState.OUTSIDE
        self.consecutive_inside_frames: int = 0
        self.consecutive_outside_frames: int = 0

        self.entry_timestamp: Optional[float] = None
        self.dwell_seconds: float = 0.0
        self.active_violation: Optional[ViolationEvent] = None
        self.escalated_to_alarm: bool = False

    def update(
        self,
        is_inside_raw: bool,
        current_time: float,
        enter_debounce_frames: int = 3,
        exit_debounce_frames: int = 5,
        camera_id: str = "default_cam",
    ) -> Tuple[Optional[ViolationEvent], Optional[ViolationEvent]]:
        """
        Updates the state machine.
        :return: (new_or_escalated_event, closed_event)
        """
        new_event: Optional[ViolationEvent] = None
        closed_event: Optional[ViolationEvent] = None

        if is_inside_raw:
            self.consecutive_inside_frames += 1
            self.consecutive_outside_frames = 0
        else:
            self.consecutive_outside_frames += 1
            self.consecutive_inside_frames = 0

        # State transition logic
        if self.state == ZoneIntrusionState.OUTSIDE:
            if is_inside_raw:
                if self.consecutive_inside_frames >= enter_debounce_frames:
                    # Confirmed intrusion
                    self.state = ZoneIntrusionState.INTRUSION
                    self.entry_timestamp = current_time
                    self.dwell_seconds = 0.0
                    self.escalated_to_alarm = False

                    # Create intrusion warning event
                    self.active_violation = ViolationEvent(
                        event_uuid=str(uuid.uuid4()),
                        track_id=self.track_id,
                        camera_id=camera_id,
                        violation_type=ViolationType.DANGER_ZONE_INTRUSION,
                        severity=ViolationSeverity.WARNING,
                        zone_name=self.zone_name,
                        start_time=current_time,
                        duration_seconds=0.0,
                    )
                    new_event = self.active_violation
                else:
                    self.state = ZoneIntrusionState.PENDING_ENTER

        elif self.state == ZoneIntrusionState.PENDING_ENTER:
            if is_inside_raw:
                if self.consecutive_inside_frames >= enter_debounce_frames:
                    self.state = ZoneIntrusionState.INTRUSION
                    self.entry_timestamp = current_time
                    self.dwell_seconds = 0.0
                    self.escalated_to_alarm = False

                    self.active_violation = ViolationEvent(
                        event_uuid=str(uuid.uuid4()),
                        track_id=self.track_id,
                        camera_id=camera_id,
                        violation_type=ViolationType.DANGER_ZONE_INTRUSION,
                        severity=ViolationSeverity.WARNING,
                        zone_name=self.zone_name,
                        start_time=current_time,
                        duration_seconds=0.0,
                    )
                    new_event = self.active_violation
            else:
                self.state = ZoneIntrusionState.OUTSIDE

        elif self.state in (ZoneIntrusionState.INTRUSION, ZoneIntrusionState.DWELL_TIMEOUT):
            if is_inside_raw:
                if self.entry_timestamp is not None:
                    self.dwell_seconds = max(0.0, current_time - self.entry_timestamp)

                # Check dwell timeout threshold
                if not self.escalated_to_alarm and self.dwell_seconds >= self.dwell_threshold:
                    self.state = ZoneIntrusionState.DWELL_TIMEOUT
                    self.escalated_to_alarm = True

                    # Escalation must maintain the SAME event_uuid
                    if self.active_violation:
                        self.active_violation.severity = ViolationSeverity.CRITICAL
                        self.active_violation.duration_seconds = self.dwell_seconds
                        self.active_violation.extra_details["escalation_reason"] = "DWELL_TIMEOUT"
                        self.active_violation.extra_details["dwell_threshold_seconds"] = self.dwell_threshold
                        new_event = self.active_violation
                    else:
                        dwell_event = ViolationEvent(
                            event_uuid=str(uuid.uuid4()),
                            track_id=self.track_id,
                            camera_id=camera_id,
                            violation_type=ViolationType.DANGER_ZONE_INTRUSION,
                            severity=ViolationSeverity.CRITICAL,
                            zone_name=self.zone_name,
                            start_time=self.entry_timestamp or current_time,
                            duration_seconds=self.dwell_seconds,
                            extra_details={"escalation_reason": "DWELL_TIMEOUT", "dwell_threshold_seconds": self.dwell_threshold},
                        )
                        self.active_violation = dwell_event
                        new_event = dwell_event
                elif self.active_violation:
                    self.active_violation.duration_seconds = self.dwell_seconds
            else:
                self.state = ZoneIntrusionState.PENDING_EXIT

        elif self.state == ZoneIntrusionState.PENDING_EXIT:
            if is_inside_raw:
                # Regained inside state, cancel exit
                self.state = (
                    ZoneIntrusionState.DWELL_TIMEOUT
                    if self.escalated_to_alarm
                    else ZoneIntrusionState.INTRUSION
                )
                if self.entry_timestamp is not None:
                    self.dwell_seconds = max(0.0, current_time - self.entry_timestamp)
                if self.active_violation:
                    self.active_violation.duration_seconds = self.dwell_seconds
            else:
                if self.consecutive_outside_frames >= exit_debounce_frames:
                    # Confirmed exit, finalize active violation
                    if self.active_violation:
                        self.active_violation.end_time = current_time
                        if self.entry_timestamp is not None:
                            self.active_violation.duration_seconds = max(0.0, current_time - self.entry_timestamp)
                        self.active_violation.status = "RESOLVED"
                        closed_event = self.active_violation
                        self.active_violation = None

                    self.state = ZoneIntrusionState.OUTSIDE
                    self.entry_timestamp = None
                    self.dwell_seconds = 0.0
                    self.escalated_to_alarm = False
                else:
                    # Still in exit debounce cooldown
                    if self.entry_timestamp is not None:
                        self.dwell_seconds = max(0.0, current_time - self.entry_timestamp)

        return new_event, closed_event


class HelmetComplianceTracker:
    """Tracks consecutive unhelmeted frames and manages helmet violation events."""

    def __init__(self, track_id: int, debounce_frames: int = 5, resolve_debounce_frames: Optional[int] = None):
        self.track_id = track_id
        self.debounce_frames = debounce_frames
        self.resolve_debounce_frames = resolve_debounce_frames if resolve_debounce_frames is not None else debounce_frames
        self.consecutive_unhelmeted: int = 0
        self.consecutive_helmeted: int = 0

        self.start_unhelmeted_time: Optional[float] = None
        self.active_violation: Optional[ViolationEvent] = None

    def update(
        self,
        has_helmet: bool,
        current_time: float,
        camera_id: str = "default_cam",
    ) -> Tuple[Optional[ViolationEvent], Optional[ViolationEvent]]:
        new_event: Optional[ViolationEvent] = None
        closed_event: Optional[ViolationEvent] = None

        if not has_helmet:
            self.consecutive_unhelmeted += 1
            self.consecutive_helmeted = 0
            if self.consecutive_unhelmeted == 1 and self.start_unhelmeted_time is None:
                self.start_unhelmeted_time = current_time

            if self.consecutive_unhelmeted >= self.debounce_frames and self.active_violation is None:
                self.active_violation = ViolationEvent(
                    event_uuid=str(uuid.uuid4()),
                    track_id=self.track_id,
                    camera_id=camera_id,
                    violation_type=ViolationType.NO_HELMET,
                    severity=ViolationSeverity.WARNING,
                    zone_name=None,
                    start_time=self.start_unhelmeted_time or current_time,
                    duration_seconds=0.0,
                    status="ACTIVE",
                )
                new_event = self.active_violation
            elif self.active_violation and self.start_unhelmeted_time:
                self.active_violation.duration_seconds = max(0.0, current_time - self.start_unhelmeted_time)
        else:
            self.consecutive_helmeted += 1
            self.consecutive_unhelmeted = 0
            if self.consecutive_helmeted >= self.resolve_debounce_frames:
                # Resolved helmet compliance
                if self.active_violation:
                    self.active_violation.end_time = current_time
                    if self.start_unhelmeted_time:
                        self.active_violation.duration_seconds = max(0.0, current_time - self.start_unhelmeted_time)
                    self.active_violation.status = "RESOLVED"
                    closed_event = self.active_violation
                    self.active_violation = None
                self.start_unhelmeted_time = None

        return new_event, closed_event


class WorkerSafetyMonitor:
    """
    Coordinates danger zone intrusion debounce, dwell timing, and helmet compliance for all active tracks.
    """

    def __init__(
        self,
        camera_id: str = "cam_01",
        enter_debounce_frames: int = 3,
        exit_debounce_frames: int = 5,
        helmet_debounce_frames: int = 5,
        helmet_resolve_debounce_frames: int = 5,
    ):
        self.camera_id = camera_id
        self.enter_debounce_frames = enter_debounce_frames
        self.exit_debounce_frames = exit_debounce_frames
        self.helmet_debounce_frames = helmet_debounce_frames
        self.helmet_resolve_debounce_frames = helmet_resolve_debounce_frames

        # Map (track_id, zone_name) -> PersonZoneTracker
        self.zone_trackers: Dict[Tuple[int, str], PersonZoneTracker] = {}
        # Map track_id -> HelmetComplianceTracker
        self.helmet_trackers: Dict[int, HelmetComplianceTracker] = {}

    def update_config(
        self,
        enter_debounce_frames: Optional[int] = None,
        exit_debounce_frames: Optional[int] = None,
        helmet_debounce_frames: Optional[int] = None,
        helmet_resolve_debounce_frames: Optional[int] = None,
    ) -> None:
        """Dynamically updates debounce thresholds received from camera configuration."""
        if enter_debounce_frames is not None:
            self.enter_debounce_frames = enter_debounce_frames
        if exit_debounce_frames is not None:
            self.exit_debounce_frames = exit_debounce_frames
        if helmet_debounce_frames is not None:
            self.helmet_debounce_frames = helmet_debounce_frames
        if helmet_resolve_debounce_frames is not None:
            self.helmet_resolve_debounce_frames = helmet_resolve_debounce_frames

    def process(
        self,
        tracked_persons: List[TrackedPerson],
        danger_zones: List[DangerZone],
        current_time: Optional[float] = None,
    ) -> Tuple[List[ViolationEvent], List[ViolationEvent]]:
        """
        Processes current frame's tracked persons against configured danger zones and helmet rules.
        :param tracked_persons: List of TrackedPerson objects (will be updated in-place with zone info)
        :param danger_zones: List of DangerZone definitions
        :param current_time: Monotonic or frame timestamp in seconds (defaults to time.monotonic())
        :return: (new_or_escalated_events, closed_events)
        """
        now = time.monotonic() if current_time is None else current_time
        new_events: List[ViolationEvent] = []
        closed_events: List[ViolationEvent] = []

        active_track_ids = {p.track_id for p in tracked_persons}

        # Clean up stale track state for removed tracks
        stale_zone_keys = [k for k in self.zone_trackers.keys() if k[0] not in active_track_ids]
        for k in stale_zone_keys:
            tracker = self.zone_trackers.pop(k)
            if tracker.active_violation:
                tracker.active_violation.end_time = now
                tracker.active_violation.status = "RESOLVED"
                closed_events.append(tracker.active_violation)

        stale_helmet_keys = [tid for tid in self.helmet_trackers.keys() if tid not in active_track_ids]
        for tid in stale_helmet_keys:
            ht = self.helmet_trackers.pop(tid)
            if ht.active_violation:
                ht.active_violation.end_time = now
                ht.active_violation.status = "RESOLVED"
                closed_events.append(ht.active_violation)

        # Process each active person
        for person in tracked_persons:
            tid = person.track_id

            # 1. Helmet compliance check
            if tid not in self.helmet_trackers:
                self.helmet_trackers[tid] = HelmetComplianceTracker(
                    track_id=tid,
                    debounce_frames=self.helmet_debounce_frames,
                    resolve_debounce_frames=self.helmet_resolve_debounce_frames,
                )
            h_new, h_closed = self.helmet_trackers[tid].update(
                has_helmet=person.has_helmet,
                current_time=now,
                camera_id=self.camera_id,
            )
            if h_new:
                new_events.append(h_new)
            if h_closed:
                closed_events.append(h_closed)

            # 2. Danger zone intrusion check
            matched_zone_name: Optional[str] = None
            max_dwell: float = 0.0
            is_in_any_zone: bool = False

            for zone in danger_zones:
                if not zone.enabled:
                    continue

                key = (tid, zone.name)
                if key not in self.zone_trackers:
                    self.zone_trackers[key] = PersonZoneTracker(
                        track_id=tid,
                        zone_name=zone.name,
                        dwell_threshold=zone.alarm_dwell_threshold_seconds,
                    )

                z_tracker = self.zone_trackers[key]
                # High-precision feet intrusion check
                raw_inside = person_in_danger_zone(person.bbox, zone.polygon)

                z_new, z_closed = z_tracker.update(
                    is_inside_raw=raw_inside,
                    current_time=now,
                    enter_debounce_frames=self.enter_debounce_frames,
                    exit_debounce_frames=self.exit_debounce_frames,
                    camera_id=self.camera_id,
                )
                if z_new:
                    new_events.append(z_new)
                if z_closed:
                    closed_events.append(z_closed)

                if z_tracker.state in (
                    ZoneIntrusionState.INTRUSION,
                    ZoneIntrusionState.DWELL_TIMEOUT,
                    ZoneIntrusionState.PENDING_EXIT,
                ):
                    is_in_any_zone = True
                    matched_zone_name = zone.name
                    if z_tracker.dwell_seconds > max_dwell:
                        max_dwell = z_tracker.dwell_seconds

            # Update person attributes in-place for visualization / downstream logic
            person.is_in_danger_zone = is_in_any_zone
            person.danger_zone_name = matched_zone_name
            person.dwell_time_seconds = max_dwell

        return new_events, closed_events
