from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from fastapi.testclient import TestClient

from agent.contracts.camera_management import MonitoringSessionResponse
from agent.contracts.chat import ToolDecision
from agent.core.config import Settings
from agent.db.base import Database
from agent.db.models import ManagedCameraModel, RectificationTaskModel, ViolationEventModel
from agent.main import create_app
from agent.services.agent_write_actions import AgentWriteActionService


def _event(event_uuid: str) -> dict[str, object]:
    return {
        "schema_version": "1.0", "event_uuid": event_uuid, "event_action": "UPSERT", "camera_id": "A01",
        "monitor_session_id": "write-action-test", "track_id": 3, "violation_type": "NO_HELMET",
        "severity": "WARNING", "status": "ACTIVE", "occurred_at_utc": datetime.now(timezone.utc).isoformat(),
        "duration_seconds": 1.0, "extra_details": {},
    }


def test_rectification_is_only_written_after_ui_confirmation() -> None:
    settings = Settings(database_url="sqlite+pysqlite:///:memory:", internal_perception_token="write-action-token", llm_provider="fake", auto_create_schema=True)
    with TestClient(create_app(settings)) as client:
        event_uuid = str(uuid4())
        assert client.post("/internal/v1/perception/events", json=_event(event_uuid), headers={"Authorization": "Bearer write-action-token"}).status_code == 200
        conversation_id = str(uuid4())
        proposal = client.post("/api/v1/agent/chat", json={
            "conversation_id": conversation_id,
            "question": f"创建整改任务：隔离危险区域，关联违规 {event_uuid}，负责人张三，截止 2026-10-01",
        })
        assert proposal.status_code == 200
        pending = proposal.json()["pending_action"]
        assert pending["action_type"] == "create_rectification_task"
        with client.app.state.database.session() as session:
            assert session.query(RectificationTaskModel).count() == 0

        confirmed = client.post(f"/api/v1/agent/actions/{pending['confirmation_id']}/confirm", json={"conversation_id": conversation_id})
        assert confirmed.status_code == 200
        result = confirmed.json()["result"]
        assert result["status"] == "PENDING"
        task_id = result["task_id"]

        repeated = client.post(f"/api/v1/agent/actions/{pending['confirmation_id']}/confirm", json={"conversation_id": conversation_id})
        assert repeated.status_code == 200
        assert repeated.json()["idempotent"] is True
        assert repeated.json()["result"]["task_id"] == task_id

        completed = client.post("/api/v1/agent/chat", json={
            "conversation_id": conversation_id,
            "question": f"完成整改任务 {task_id}",
        }).json()["pending_action"]
        finished = client.post(f"/api/v1/agent/actions/{completed['confirmation_id']}/confirm", json={"conversation_id": conversation_id})
        assert finished.status_code == 200
        assert finished.json()["result"]["violation_resolved"] is True
        with client.app.state.database.session() as session:
            assert session.get(ViolationEventModel, event_uuid).status == "RESOLVED"


class _FakeCameraManagement:
    def __init__(self) -> None:
        self.calls: list[str] = []

    def get_camera_and_node(self, camera_id: str):
        return SimpleNamespace(camera_id=camera_id, display_name="东门摄像头"), SimpleNamespace(node_id="node-1")

    def start_camera(self, camera_id: str) -> MonitoringSessionResponse:
        self.calls.append(f"start:{camera_id}")
        return MonitoringSessionResponse(camera_id=camera_id, node_id="node-1", desired_state="RUNNING", accepted=True)

    def stop_camera(self, camera_id: str) -> MonitoringSessionResponse:
        self.calls.append(f"stop:{camera_id}")
        return MonitoringSessionResponse(camera_id=camera_id, node_id="node-1", desired_state="STOPPED", accepted=True)


class _SelectionModel:
    model_name = "selection-test"

    def decide(self, question, previous_results, memory_context="", tool_catalog=()):
        if previous_results:
            return None
        if "整改" in question:
            return ToolDecision(tool_name="list_rectification_targets", purpose="列出可选整改目标")
        return ToolDecision(tool_name="list_monitoring_targets", selection_action="stop", purpose="列出可停止监控的摄像头")

    def respond(self, question, results, memory_context=""):
        return "unused"


def test_camera_control_is_not_called_until_confirmation() -> None:
    database = Database("sqlite+pysqlite:///:memory:")
    database.create_schema()
    camera = _FakeCameraManagement()
    service = AgentWriteActionService(database, camera)  # type: ignore[arg-type]
    proposed = service.propose("browser-conversation", ToolDecision(tool_name="start_monitoring", camera_id="A01", purpose="启动监控"))
    assert camera.calls == []
    executed = service.confirm(proposed.confirmation_id, "browser-conversation")
    assert camera.calls == ["start:A01"]
    assert executed.status == "EXECUTED"


def test_ambiguous_write_requests_return_clickable_safe_target_options() -> None:
    settings = Settings(database_url="sqlite+pysqlite:///:memory:", internal_perception_token="guided-choice-token", llm_provider="fake", auto_create_schema=True)
    with TestClient(create_app(settings)) as client:
        client.app.state.chat_service.model = _SelectionModel()
        event_uuid = str(uuid4())
        assert client.post("/internal/v1/perception/events", json=_event(event_uuid), headers={"Authorization": "Bearer guided-choice-token"}).status_code == 200
        with client.app.state.database.session() as session:
            session.add(ManagedCameraModel(
                camera_id="cam_field_01", display_name="现场主摄像头", node_id="node-1", source_type="file",
                source_uri_encrypted="not-used-for-selection", source_uri_masked="file://…/demo.mp4", desired_state="RUNNING",
            ))

        rectification = client.post("/api/v1/agent/chat", json={"question": "创建整改任务"})
        assert rectification.status_code == 200
        rectification_body = rectification.json()
        assert rectification_body["guided_selection"]["kind"] == "RECTIFICATION_TARGET"
        assert rectification_body["guided_selection"]["options"][0]["option_id"] == event_uuid
        assert rectification_body["evidence"][0]["snapshot_uri"] is None

        camera = client.post("/api/v1/agent/chat", json={"question": "关闭摄像头"})
        assert camera.status_code == 200
        camera_body = camera.json()
        assert camera_body["guided_selection"]["kind"] == "CAMERA_TARGET"
        option = camera_body["guided_selection"]["options"][0]
        assert option["option_id"] == "cam_field_01"
        assert option["follow_up_question"] == "停止 cam_field_01 监控"


def test_rectification_task_center_lists_details_and_manual_confirmed_updates() -> None:
    settings = Settings(database_url="sqlite+pysqlite:///:memory:", internal_perception_token="task-center-token", llm_provider="fake", auto_create_schema=True)
    with TestClient(create_app(settings)) as client:
        event_uuid = str(uuid4())
        assert client.post("/internal/v1/perception/events", json=_event(event_uuid), headers={"Authorization": "Bearer task-center-token"}).status_code == 200
        conversation_id = "task-center-browser"
        created = client.post("/api/v1/rectification-tasks/pending-create", json={
            "conversation_id": conversation_id, "event_uuid": event_uuid, "title": "补齐安全帽",
            "description": "班前完成", "owner": "李四", "due_at_utc": "2026-10-01T10:00:00Z",
        })
        assert created.status_code == 200
        action_id = created.json()["pending_action"]["confirmation_id"]
        confirmed = client.post(f"/api/v1/agent/actions/{action_id}/confirm", json={"conversation_id": conversation_id})
        assert confirmed.status_code == 200
        task_id = confirmed.json()["result"]["task_id"]

        page = client.get("/api/v1/rectification-tasks", params={"status": "PENDING", "owner": "李"})
        assert page.status_code == 200
        assert page.json()["total"] == 1
        assert page.json()["items"][0]["task_id"] == task_id

        detail = client.get(f"/api/v1/rectification-tasks/{task_id}")
        assert detail.status_code == 200
        assert detail.json()["violation"]["event_uuid"] == event_uuid
        assert detail.json()["audits"][0]["action"] == "CREATED"

        update = client.post(f"/api/v1/rectification-tasks/{task_id}/pending-update", json={
            "conversation_id": conversation_id, "status": "COMPLETED", "note": "已现场核验",
        })
        assert update.status_code == 200
        update_action = update.json()["pending_action"]["confirmation_id"]
        assert client.post(f"/api/v1/agent/actions/{update_action}/confirm", json={"conversation_id": conversation_id}).status_code == 200
        done = client.get("/api/v1/rectification-tasks", params={"status": "COMPLETED"}).json()
        assert done["items"][0]["status"] == "COMPLETED"
        rejected = client.post(f"/api/v1/rectification-tasks/{task_id}/pending-update", json={
            "conversation_id": conversation_id, "owner": "王五",
        })
        assert rejected.status_code == 409
        assert "不可再编辑" in rejected.json()["detail"]
        with client.app.state.database.session() as session:
            assert session.get(ViolationEventModel, event_uuid).status == "RESOLVED"
