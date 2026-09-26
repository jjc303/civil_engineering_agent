from fastapi.testclient import TestClient

from agent.core.config import Settings
from agent.main import create_app


def test_camera_list_includes_config_only_camera_as_offline(tmp_path) -> None:
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        internal_perception_token="web-contract-token",
        llm_provider="fake",
        auto_create_schema=True,
        media_root=str(tmp_path / "media"),
    )
    with TestClient(create_app(settings)) as client:
        response = client.put("/api/v1/cameras/cam-config-only/zones", json={
            "source_resolution": {"width": 1920, "height": 1080},
            "zones": [],
        })
        assert response.status_code == 200

        cameras = client.get("/api/v1/cameras")
        assert cameras.status_code == 200
        camera = cameras.json()[0]
        assert camera["camera_id"] == "cam-config-only"
        assert camera["monitor_session_id"] == "unreported"
        assert camera["is_online"] is False
        assert camera["fps"] == 0.0
        assert camera["reported_at_utc"]


def test_media_mount_and_cors_preflight(tmp_path) -> None:
    media_root = tmp_path / "media"
    snapshot = media_root / "snapshots" / "20260925" / "evidence.jpg"
    snapshot.parent.mkdir(parents=True)
    snapshot.write_bytes(b"fixture-image")
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        internal_perception_token="web-contract-token",
        llm_provider="fake",
        auto_create_schema=True,
        media_root=str(media_root),
    )
    with TestClient(create_app(settings)) as client:
        media = client.get("/media/snapshots/20260925/evidence.jpg")
        assert media.status_code == 200
        assert media.content == b"fixture-image"
        assert client.get("/media/snapshots/20260925/missing.jpg").status_code == 404

        preflight = client.options("/api/v1/cameras", headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "GET",
        })
        assert preflight.status_code == 200
        assert preflight.headers["access-control-allow-origin"] == "http://localhost:5173"
