from cryptography.fernet import Fernet
from fastapi.testclient import TestClient

from agent.core.config import Settings
from agent.main import create_app


def _settings() -> Settings:
    return Settings(
        database_url="sqlite+pysqlite:///:memory:",
        internal_perception_token="perception-token",
        admin_token="admin-token",
        credential_encryption_key=Fernet.generate_key().decode(),
        llm_provider="fake",
        auto_create_schema=True,
    )


def test_cv_node_camera_source_and_heartbeat_are_protected(monkeypatch) -> None:
    with TestClient(create_app(_settings())) as client:
        headers = {"Authorization": "Bearer admin-token"}
        missing_admin = client.get("/api/v1/cv-nodes")
        assert missing_admin.status_code == 401

        node = client.post("/api/v1/cv-nodes", headers=headers, json={
            "node_id": "cv-east-01", "display_name": "东区 GPU 节点", "control_url": "http://cv-east.local:8100", "capacity": 4,
        })
        assert node.status_code == 201
        node_body = node.json()
        assert node_body["control_token"]
        assert node_body["is_online"] is False

        heartbeat = client.put(
            "/internal/v1/cv-nodes/cv-east-01/heartbeat",
            headers={"Authorization": f"Bearer {node_body['control_token']}"},
            json={"active_sessions": 1, "capacity": 4},
        )
        assert heartbeat.status_code == 200
        assert heartbeat.json()["is_online"] is True

        created = client.post("/api/v1/managed-cameras", headers=headers, json={
            "camera_id": "cam-field-01", "display_name": "东侧塔吊", "node_id": "cv-east-01",
            "source_type": "rtsp", "source_uri": "rtsp://operator:secret@10.0.0.8:554/live",
        })
        assert created.status_code == 201
        assert "secret" not in created.json()["source_uri_masked"]
        assert created.json()["desired_state"] == "STOPPED"

        listed = client.get("/api/v1/managed-cameras", headers=headers)
        assert listed.status_code == 200
        assert listed.json()[0]["camera_id"] == "cam-field-01"

        renamed = client.put("/api/v1/managed-cameras/cam-field-01/source", headers=headers, json={
            "display_name": "东侧塔吊（已更新）", "node_id": "cv-east-01", "source_type": "rtsp",
        })
        assert renamed.status_code == 200
        assert renamed.json()["display_name"] == "东侧塔吊（已更新）"

        called: dict[str, object] = {}

        class _Response:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict[str, str]:
                return {"monitor_session_id": "session-cam-field-01"}

        class FakeClient:
            def __init__(self, **_kwargs) -> None:
                pass

            def __enter__(self):
                return self

            def __exit__(self, *_args) -> None:
                return None

            def request(self, _method: str, url: str, **kwargs):
                called["url"] = url
                called["payload"] = kwargs["json"]
                return _Response()

            def get(self, url: str, **_kwargs):
                called["media_url"] = url
                if url.endswith("/preview.jpg"):
                    return _JpegResponse()
                return _MediaResponse()

        class _MediaResponse:
            def raise_for_status(self) -> None:
                return None

            def json(self) -> dict[str, object]:
                return {
                    "current_path": "/srv/videos", "parent_path": None,
                    "directories": [{"name": "demo", "path": "/srv/videos/demo"}],
                    "files": [{"name": "walk.mp4", "path": "/srv/videos/walk.mp4"}],
                }

        class _JpegResponse:
            content = b"jpeg-frame"

            def raise_for_status(self) -> None:
                return None

        monkeypatch.setattr("agent.services.camera_management.httpx.Client", FakeClient)
        started = client.post("/api/v1/cameras/cam-field-01/monitoring:start", headers=headers)
        assert started.status_code == 202
        assert started.json()["desired_state"] == "RUNNING"
        assert called["url"] == "http://cv-east.local:8100/control/v1/sessions"
        assert called["payload"] == {
            "camera_id": "cam-field-01",
            "source_type": "rtsp",
            "source_uri": "rtsp://operator:secret@10.0.0.8:554/live",
        }

        media = client.get("/api/v1/cv-nodes/cv-east-01/media-files", headers=headers)
        assert media.status_code == 200
        assert media.json()["files"][0]["path"] == "/srv/videos/walk.mp4"
        assert called["media_url"] == "http://cv-east.local:8100/control/v1/media-files"

        preview = client.get("/api/v1/cameras/cam-field-01/preview.jpg")
        assert preview.status_code == 200
        assert preview.headers["content-type"] == "image/jpeg"
        assert preview.content == b"jpeg-frame"

        blocked_update = client.put("/api/v1/managed-cameras/cam-field-01/source", headers=headers, json={
            "display_name": "运行中不能改", "node_id": "cv-east-01", "source_type": "rtsp",
        })
        assert blocked_update.status_code == 503
