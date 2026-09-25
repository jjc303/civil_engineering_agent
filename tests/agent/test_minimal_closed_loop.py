from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from agent.core.config import Settings
from agent.main import create_app


@pytest.fixture
def client() -> TestClient:
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        internal_perception_token="contract-test-token",
        auto_create_schema=True,
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


@pytest.fixture
def internal_headers() -> dict[str, str]:
    return {"Authorization": "Bearer contract-test-token"}


def event_payload(event_uuid: str, **overrides: object) -> dict[str, object]:
    occurred_at = datetime(2026, 9, 25, 8, 0, tzinfo=timezone.utc)
    payload: dict[str, object] = {
        "schema_version": "1.0",
        "event_uuid": event_uuid,
        "event_action": "UPSERT",
        "camera_id": "camera-a01",
        "monitor_session_id": "session-20260925-a01",
        "track_id": 42,
        "violation_type": "DANGER_ZONE_INTRUSION",
        "severity": "WARNING",
        "status": "ACTIVE",
        "zone_id": "zone-crane",
        "zone_name": "吊装危险区",
        "occurred_at_utc": occurred_at.isoformat(),
        "resolved_at_utc": None,
        "duration_seconds": 0,
        "snapshot_uri": "snapshots/20260925/evidence.jpg",
        "model_name": "yolov8n",
        "model_version": "2026.09.25",
        "extra_details": {"zone_config_version": "v3"},
    }
    payload.update(overrides)
    return payload


def test_event_is_idempotently_upserted_and_queryable(client: TestClient, internal_headers: dict[str, str]) -> None:
    event_uuid = str(uuid4())
    created = client.post("/internal/v1/perception/events", json=event_payload(event_uuid), headers=internal_headers)
    assert created.status_code == 200
    assert created.json()["operation"] == "CREATED"

    resolved_at = datetime(2026, 9, 25, 8, 0, 12, tzinfo=timezone.utc)
    updated = client.post(
        "/internal/v1/perception/events",
        json=event_payload(
            event_uuid,
            severity="CRITICAL",
            status="RESOLVED",
            resolved_at_utc=resolved_at.isoformat(),
            duration_seconds=12,
        ),
        headers=internal_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["operation"] == "UPDATED"
    assert updated.json()["status"] == "RESOLVED"

    violations = client.get("/api/v1/violations", params={"camera_id": "camera-a01"})
    assert violations.status_code == 200
    assert len(violations.json()) == 1
    assert violations.json()[0]["event_uuid"] == event_uuid
    assert violations.json()[0]["severity"] == "CRITICAL"
    assert violations.json()[0]["duration_seconds"] == 12

    statistics = client.get("/api/v1/violations/statistics")
    assert statistics.status_code == 200
    assert statistics.json() == {
        "total_violations": 1,
        "average_duration_seconds": 12.0,
        "by_type": {"DANGER_ZONE_INTRUSION": 1},
        "by_severity": {"CRITICAL": 1},
    }

    agent_query = client.post("/api/v1/agent/safety-query", json={"operation": "statistics"})
    assert agent_query.status_code == 200
    assert agent_query.json()["result"]["total_violations"] == 1


def test_camera_status_and_input_boundaries(client: TestClient, internal_headers: dict[str, str]) -> None:
    report = {
        "camera_id": "camera-a01",
        "monitor_session_id": "session-20260925-a01",
        "is_online": True,
        "fps": 24.5,
        "processed_frame_id": 108,
        "active_workers_count": 3,
        "model_name": "yolov8n",
        "model_version": "2026.09.25",
        "reported_at_utc": datetime.now(timezone.utc).isoformat(),
        "extra_details": {"queue_depth": 0},
    }
    response = client.put("/internal/v1/perception/cameras/camera-a01/status", json=report, headers=internal_headers)
    assert response.status_code == 200
    status = client.get("/api/v1/cameras/camera-a01/status")
    assert status.status_code == 200
    assert status.json()["fps"] == 24.5

    graph_status = client.post("/api/v1/agent/safety-query", json={"operation": "camera_status", "camera_id": "camera-a01"})
    assert graph_status.status_code == 200
    assert graph_status.json()["result"]["is_online"] is True

    unauthenticated = client.post("/internal/v1/perception/events", json=event_payload(str(uuid4())))
    assert unauthenticated.status_code == 401

    invalid = client.post(
        "/internal/v1/perception/events",
        json=event_payload(str(uuid4()), snapshot_uri="/host/private/evidence.jpg"),
        headers=internal_headers,
    )
    assert invalid.status_code == 422

    unresolved_time = datetime.now(timezone.utc)
    invalid_resolution = client.post(
        "/internal/v1/perception/events",
        json=event_payload(
            str(uuid4()),
            status="RESOLVED",
            resolved_at_utc=(unresolved_time - timedelta(seconds=1)).isoformat(),
            occurred_at_utc=unresolved_time.isoformat(),
        ),
        headers=internal_headers,
    )
    assert invalid_resolution.status_code == 422
