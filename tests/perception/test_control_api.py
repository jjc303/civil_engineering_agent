from pathlib import Path

from fastapi.testclient import TestClient

from perception.control_api import CvControlSettings, create_control_app
from perception.services.session_runner import CivilSafetyPerceptionService
from perception.storage.event_store import EventStore


def test_control_api_requires_node_token_and_rejects_invalid_source(tmp_path: Path) -> None:
    (tmp_path / "clip.mp4").touch()
    (tmp_path / "nested").mkdir()
    (tmp_path / "notes.txt").touch()
    settings = CvControlSettings(
        node_id="test-node",
        node_token="test-token",
        agent_url="http://agent.invalid",
        internal_perception_token="internal-token",
        allowed_media_roots=(tmp_path,),
        heartbeat_interval_seconds=3600,
    )
    service = CivilSafetyPerceptionService(event_store=EventStore(db_path=str(tmp_path / "events.db")))
    with TestClient(create_control_app(settings, service)) as client:
        assert client.get("/control/v1/health").status_code == 403
        assert client.get("/control/v1/health", headers={"Authorization": "Bearer test-token"}).status_code == 200
        media = client.get("/control/v1/media-files", headers={"Authorization": "Bearer test-token"})
        assert media.status_code == 200
        assert "nested" in [item["name"] for item in media.json()["directories"]]
        assert [item["name"] for item in media.json()["files"]] == ["clip.mp4"]
        invalid = client.post(
            "/control/v1/sessions",
            headers={"Authorization": "Bearer test-token"},
            json={"camera_id": "cam-01", "source_type": "rtsp", "source_uri": "http://not-rtsp"},
        )
        assert invalid.status_code == 422
