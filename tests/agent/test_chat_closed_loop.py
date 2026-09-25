from datetime import datetime, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from agent.core.config import Settings
from agent.main import create_app


@pytest.fixture
def client() -> TestClient:
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        internal_perception_token="chat-contract-token",
        auto_create_schema=True,
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def _headers() -> dict[str, str]:
    return {"Authorization": "Bearer chat-contract-token"}


def _event(event_uuid: str) -> dict[str, object]:
    return {
        "schema_version": "1.0",
        "event_uuid": event_uuid,
        "event_action": "UPSERT",
        "camera_id": "A01",
        "monitor_session_id": "chat-test-session",
        "track_id": 7,
        "violation_type": "DANGER_ZONE_INTRUSION",
        "severity": "CRITICAL",
        "status": "ACTIVE",
        "occurred_at_utc": datetime(2026, 9, 25, 12, 30, tzinfo=timezone.utc).isoformat(),
        "duration_seconds": 4.0,
        "snapshot_uri": "snapshots/20260925/chat-test.jpg",
        "extra_details": {},
    }


def test_chat_uses_bounded_tools_and_returns_event_evidence(client: TestClient) -> None:
    event_uuid = str(uuid4())
    seeded = client.post("/internal/v1/perception/events", json=_event(event_uuid), headers=_headers())
    assert seeded.status_code == 200

    response = client.post("/api/v1/agent/chat", json={"question": "A01 摄像头有多少严重违规？最近一条是什么？"})
    assert response.status_code == 200
    body = response.json()
    assert body["degraded"] is False
    assert "共有 1 条违规" in body["answer"]
    assert "最近一条" in body["answer"]
    assert [item["tool_name"] for item in body["tool_trace"]] == ["get_violation_statistics", "query_violations"]
    assert body["evidence"] == [{
        "event_uuid": event_uuid,
        "occurred_at_utc": "2026-09-25T12:30:00Z",
        "snapshot_uri": "snapshots/20260925/chat-test.jpg",
    }]


def test_chat_queries_camera_status_and_rejects_blank_question(client: TestClient) -> None:
    report = {
        "camera_id": "A01",
        "monitor_session_id": "chat-test-session",
        "is_online": True,
        "fps": 25.0,
        "processed_frame_id": 99,
        "active_workers_count": 2,
        "reported_at_utc": datetime.now(timezone.utc).isoformat(),
        "extra_details": {},
    }
    assert client.put("/internal/v1/perception/cameras/A01/status", json=report, headers=_headers()).status_code == 200

    response = client.post("/api/v1/agent/chat", json={"question": "A01 摄像头状态如何？"})
    assert response.status_code == 200
    assert response.json()["tool_trace"][0]["tool_name"] == "get_camera_status"
    assert "当前在线" in response.json()["answer"]

    blank = client.post("/api/v1/agent/chat", json={"question": "   "})
    assert blank.status_code == 422
