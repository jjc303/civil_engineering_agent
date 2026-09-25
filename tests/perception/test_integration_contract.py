from __future__ import annotations

import json
import sqlite3
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict

import pytest
import requests

from perception.schemas.contract_v1 import (
    AgentEventResponseV1,
    CameraRunConfigContractV1,
    CameraStatusContractV1,
    PerceptionEventContractV1,
    TimeAnchor,
    to_event_contract_v1,
)
from perception.schemas.detection import (
    BoundingBox,
    DangerZone,
    TrackedPerson,
    ViolationEvent,
    ViolationSeverity,
    ViolationType,
)
from perception.services.event_publisher import OutboxStore, PerceptionEventPublisher
from perception.tracking.state_machine import (
    PersonZoneTracker,
    WorkerSafetyMonitor,
    ZoneIntrusionState,
)


def _make_tracked_person(track_id: int, cx: float, cy: float, has_helmet: bool = True) -> TrackedPerson:
    bbox = BoundingBox(
        x1=cx - 25.0,
        y1=cy - 100.0,
        x2=cx + 25.0,
        y2=cy,
        conf=0.9,
        class_id=0,
        class_name="person",
        has_helmet=has_helmet,
    )
    return TrackedPerson(
        track_id=track_id,
        bbox=bbox,
        feet_point=(cx, cy),
        has_helmet=has_helmet,
    )


# ==============================================================================
# 1. Detail 2: Precision TimeAnchor (Monotonic to UTC offset)
# ==============================================================================
def test_time_anchor_precision_and_offset():
    utc_start = datetime(2026, 9, 25, 10, 0, 0, tzinfo=timezone.utc)
    mono_start = 1000.0

    anchor = TimeAnchor(
        session_started_at_utc=utc_start,
        session_started_monotonic=mono_start,
    )

    # 15.5 seconds later
    mono_event = 1015.5
    utc_event = anchor.to_utc(mono_event)

    expected_utc = datetime(2026, 9, 25, 10, 0, 15, 500000, tzinfo=timezone.utc)
    assert utc_event == expected_utc
    assert anchor.to_utc_iso(mono_event) == "2026-09-25T10:00:15Z"


# ==============================================================================
# 2. Detail 1: Lifecycle Invariant event_uuid (Enter -> Escalation -> Exit)
# ==============================================================================
def test_event_lifecycle_invariant_uuid_and_contract_v1():
    tracker = PersonZoneTracker(track_id=101, zone_name="Crane_Area", dwell_threshold=4.0)
    utc_anchor = TimeAnchor(
        session_started_at_utc=datetime(2026, 9, 25, 12, 0, 0, tzinfo=timezone.utc),
        session_started_monotonic=100.0,
    )
    session_id = "session_test_001"

    # Step 1: Confirmed Entry at monotonic 100.3s
    tracker.update(is_inside_raw=True, current_time=100.1, enter_debounce_frames=3)
    tracker.update(is_inside_raw=True, current_time=100.2, enter_debounce_frames=3)
    ev_enter, _ = tracker.update(
        is_inside_raw=True, current_time=100.3, enter_debounce_frames=3, camera_id="cam_01"
    )

    assert ev_enter is not None
    initial_uuid = ev_enter.event_uuid
    assert ev_enter.status == "ACTIVE"
    assert ev_enter.severity == ViolationSeverity.WARNING

    # Convert to Contract v1
    c1 = to_event_contract_v1(
        event=ev_enter,
        time_anchor=utc_anchor,
        monitor_session_id=session_id,
        zone_id="zone_crane_01",
        relative_snapshot_uri="snapshots/20260925/enter.jpg",
    )
    assert c1.event_uuid == initial_uuid
    assert c1.status == "ACTIVE"
    assert c1.severity == "WARNING"
    assert c1.violation_type == "DANGER_ZONE_INTRUSION"
    assert c1.occurred_at_utc == "2026-09-25T12:00:00Z"
    assert c1.resolved_at_utc is None
    assert c1.snapshot_uri == "snapshots/20260925/enter.jpg"

    # Step 2: Dwell Timeout Escalation at monotonic 104.5s (4.2s inside >= 4.0s threshold)
    ev_escalated, _ = tracker.update(
        is_inside_raw=True, current_time=104.5, enter_debounce_frames=3, camera_id="cam_01"
    )
    assert ev_escalated is not None
    # Crucial Rule 1: SAME event_uuid!
    assert ev_escalated.event_uuid == initial_uuid
    assert ev_escalated.status == "ACTIVE"
    assert ev_escalated.severity == ViolationSeverity.CRITICAL
    assert ev_escalated.extra_details.get("escalation_reason") == "DWELL_TIMEOUT"

    c2 = to_event_contract_v1(
        event=ev_escalated,
        time_anchor=utc_anchor,
        monitor_session_id=session_id,
        zone_id="zone_crane_01",
    )
    assert c2.event_uuid == initial_uuid
    assert c2.status == "ACTIVE"
    assert c2.severity == "CRITICAL"
    assert c2.extra_details["escalation_reason"] == "DWELL_TIMEOUT"
    assert c2.duration_seconds == pytest.approx(4.2, 0.05)

    # Step 3: Exit danger zone (exit debounce = 3 frames)
    tracker.update(is_inside_raw=False, current_time=105.0, exit_debounce_frames=3)
    tracker.update(is_inside_raw=False, current_time=105.1, exit_debounce_frames=3)
    _, ev_resolved = tracker.update(
        is_inside_raw=False, current_time=105.2, exit_debounce_frames=3
    )

    assert ev_resolved is not None
    # Crucial Rule 1: SAME event_uuid, now RESOLVED!
    assert ev_resolved.event_uuid == initial_uuid
    assert ev_resolved.status == "RESOLVED"
    assert ev_resolved.end_time == 105.2

    c3 = to_event_contract_v1(
        event=ev_resolved,
        time_anchor=utc_anchor,
        monitor_session_id=session_id,
        zone_id="zone_crane_01",
    )
    assert c3.event_uuid == initial_uuid
    assert c3.status == "RESOLVED"
    assert c3.resolved_at_utc == "2026-09-25T12:00:05Z"
    assert c3.duration_seconds > 4.5


# ==============================================================================
# 3. Detail 3: Configurable Debounce Parameters
# ==============================================================================
def test_configurable_debounce_thresholds():
    monitor = WorkerSafetyMonitor(
        camera_id="cam_custom",
        enter_debounce_frames=2,
        exit_debounce_frames=4,
        helmet_debounce_frames=2,
        helmet_resolve_debounce_frames=4,
    )
    assert monitor.enter_debounce_frames == 2
    assert monitor.exit_debounce_frames == 4

    # Update via dynamic configuration
    monitor.update_config(
        enter_debounce_frames=5,
        exit_debounce_frames=7,
        helmet_debounce_frames=3,
        helmet_resolve_debounce_frames=6,
    )
    assert monitor.enter_debounce_frames == 5
    assert monitor.exit_debounce_frames == 7
    assert monitor.helmet_debounce_frames == 3
    assert monitor.helmet_resolve_debounce_frames == 6


# ==============================================================================
# 4. Detail 4: Outbox Table, Idempotent Delivery, Retries & Client Error Handling
# ==============================================================================
class MockResponse:
    def __init__(self, status_code: int, json_data: dict, text: str = ""):
        self.status_code = status_code
        self._json_data = json_data
        self.text = text or json.dumps(json_data)

    def json(self):
        return self._json_data


def test_outbox_store_persistence_and_schema(tmp_path):
    db_file = tmp_path / "outbox.db"
    store = OutboxStore(db_file)

    # Verify table schema directly via SQLite PRAGMA
    with sqlite3.connect(str(db_file)) as conn:
        cols = {
            row[1] for row in conn.execute("PRAGMA table_info(outbox_events);").fetchall()
        }
    expected_cols = {
        "event_uuid",
        "payload_json",
        "retry_count",
        "next_retry_at",
        "last_error",
        "created_at",
        "delivered_at",
    }
    assert expected_cols.issubset(cols)

    # Test enqueue
    event_id = "test-uuid-001"
    store.enqueue(event_id, {"msg": "hello", "step": 1})
    rec = store.get_event(event_id)
    assert rec is not None
    assert rec["delivered_at"] is None
    assert json.loads(rec["payload_json"])["step"] == 1

    # Test idempotent re-enqueue of same event (e.g. escalated status)
    store.enqueue(event_id, {"msg": "hello", "step": 2})
    rec_updated = store.get_event(event_id)
    assert json.loads(rec_updated["payload_json"])["step"] == 2
    assert rec_updated["delivered_at"] is None

    # Test mark delivered
    store.mark_delivered(event_id)
    rec_deliv = store.get_event(event_id)
    assert rec_deliv["delivered_at"] is not None

    # Test get_pending doesn't return delivered
    assert len(store.get_pending()) == 0


def test_publisher_successful_delivery(tmp_path, monkeypatch):
    db_file = tmp_path / "outbox.db"
    session = requests.Session()

    def mock_post(url, json, headers, timeout):
        assert "/internal/v1/perception/events" in url
        assert headers["Content-Type"] == "application/json"
        assert headers["Authorization"] == "Bearer secret_token_123"
        return MockResponse(
            201,
            {
                "event_uuid": json["event_uuid"],
                "operation": "CREATED",
                "status": "ACTIVE",
                "server_received_at_utc": "2026-09-25T14:00:00Z",
            },
        )

    monkeypatch.setattr(session, "post", mock_post)

    publisher = PerceptionEventPublisher(
        agent_base_url="http://agent-api.local",
        db_path=db_file,
        bearer_token="secret_token_123",
        session=session,
    )

    sample_event = PerceptionEventContractV1(
        event_uuid="event-success-001",
        camera_id="cam_01",
        monitor_session_id="session_01",
        track_id=1,
        violation_type="DANGER_ZONE_INTRUSION",
        severity="WARNING",
        status="ACTIVE",
        occurred_at_utc="2026-09-25T14:00:00Z",
    )

    success, resp = publisher.publish(sample_event)
    assert success is True
    assert resp is not None
    assert resp.operation == "CREATED"

    # Verify event is marked delivered in Outbox
    rec = publisher.outbox.get_event("event-success-001")
    assert rec["delivered_at"] is not None
    assert rec["last_error"] is None


def test_publisher_client_error_422_no_retry(tmp_path, monkeypatch):
    db_file = tmp_path / "outbox.db"
    session = requests.Session()

    def mock_post(url, json, headers, timeout):
        return MockResponse(
            422,
            {"detail": "Unprocessable Entity: invalid zone_id format"},
            text="Unprocessable Entity",
        )

    monkeypatch.setattr(session, "post", mock_post)

    publisher = PerceptionEventPublisher(
        agent_base_url="http://agent-api.local",
        db_path=db_file,
        session=session,
    )

    sample_event = PerceptionEventContractV1(
        event_uuid="event-err-422",
        camera_id="cam_01",
        monitor_session_id="session_01",
        track_id=1,
        violation_type="DANGER_ZONE_INTRUSION",
        severity="WARNING",
        status="ACTIVE",
        occurred_at_utc="2026-09-25T14:00:00Z",
    )

    success, resp = publisher.publish(sample_event)
    assert success is False
    assert resp is None

    # Verify event is NOT marked delivered and next_retry_at is infinity (no auto retry)
    rec = publisher.outbox.get_event("event-err-422")
    assert rec["delivered_at"] is None
    assert rec["next_retry_at"] >= 1e11
    assert "422" in rec["last_error"]


def test_publisher_server_error_500_with_backoff_and_flush(tmp_path, monkeypatch):
    db_file = tmp_path / "outbox.db"
    session = requests.Session()

    attempts = {"count": 0}

    def mock_post(url, json, headers, timeout):
        attempts["count"] += 1
        if attempts["count"] == 1:
            # First attempt: 500 error
            return MockResponse(500, {}, text="Internal Server Error")
        else:
            # Subsequent attempt: Agent recovered!
            return MockResponse(
                200,
                {
                    "event_uuid": json["event_uuid"],
                    "operation": "CREATED",
                    "status": "ACTIVE",
                    "server_received_at_utc": "2026-09-25T14:05:00Z",
                },
            )

    monkeypatch.setattr(session, "post", mock_post)

    publisher = PerceptionEventPublisher(
        agent_base_url="http://agent-api.local",
        db_path=db_file,
        session=session,
    )

    sample_event = PerceptionEventContractV1(
        event_uuid="event-retry-500",
        camera_id="cam_01",
        monitor_session_id="session_01",
        track_id=1,
        violation_type="DANGER_ZONE_INTRUSION",
        severity="WARNING",
        status="ACTIVE",
        occurred_at_utc="2026-09-25T14:00:00Z",
    )

    # Initial publish fails due to 500
    success, resp = publisher.publish(sample_event)
    assert success is False
    rec = publisher.outbox.get_event("event-retry-500")
    assert rec["delivered_at"] is None
    assert rec["retry_count"] == 1

    # Simulate retry timer elapsed
    with sqlite3.connect(str(db_file)) as conn:
        conn.execute("UPDATE outbox_events SET next_retry_at = 0 WHERE event_uuid = 'event-retry-500'")
        conn.commit()

    # Flush outbox
    flushed = publisher.flush_outbox()
    assert flushed == 1

    rec_after = publisher.outbox.get_event("event-retry-500")
    assert rec_after["delivered_at"] is not None
