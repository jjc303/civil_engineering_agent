import pytest
from fastapi.testclient import TestClient

from agent.core.config import Settings
from agent.main import create_app


@pytest.fixture
def client() -> TestClient:
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        internal_perception_token="config-contract-token",
        auto_create_schema=True,
    )
    with TestClient(create_app(settings)) as test_client:
        yield test_client


def config_payload(**overrides: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "source_resolution": {"width": 1920, "height": 1080},
        "enter_debounce_frames": 3,
        "exit_debounce_frames": 5,
        "helmet_debounce_frames": 5,
        "alarm_dwell_threshold_seconds": 5.0,
        "zones": [{
            "zone_id": "zone-crane",
            "zone_name": "吊装危险区",
            "polygon": [[100, 100], [500, 100], [500, 400], [100, 400]],
            "enabled": True,
            "alarm_dwell_threshold_seconds": 5.0,
        }],
    }
    payload.update(overrides)
    return payload


def test_versioned_camera_config_is_written_and_read_by_cv(client: TestClient) -> None:
    created = client.put("/api/v1/cameras/cam-a01/zones", json=config_payload())
    assert created.status_code == 200
    assert created.json()["config_version"] == 1

    headers = {"Authorization": "Bearer config-contract-token"}
    fetched = client.get("/internal/v1/perception/cameras/cam-a01/config", headers=headers)
    assert fetched.status_code == 200
    assert fetched.json()["zones"][0]["zone_id"] == "zone-crane"

    updated = client.put("/api/v1/cameras/cam-a01/zones", json=config_payload(expected_version=1, enter_debounce_frames=7))
    assert updated.status_code == 200
    assert updated.json()["config_version"] == 2
    assert updated.json()["enter_debounce_frames"] == 7

    stale = client.put("/api/v1/cameras/cam-a01/zones", json=config_payload(expected_version=1))
    assert stale.status_code == 409


def test_camera_config_requires_internal_token_and_valid_polygon(client: TestClient) -> None:
    assert client.get("/internal/v1/perception/cameras/missing/config").status_code == 401
    invalid = client.put("/api/v1/cameras/cam-a01/zones", json=config_payload(zones=[{
        "zone_id": "bad", "zone_name": "坏围栏", "polygon": [[1, 2], [3, 4]],
    }]))
    assert invalid.status_code == 422
