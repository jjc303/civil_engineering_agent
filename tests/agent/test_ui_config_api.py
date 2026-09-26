from fastapi.testclient import TestClient

from agent.core.config import Settings
from agent.main import create_app


def test_admin_publishes_versioned_ui_config_and_public_reads_it() -> None:
    settings = Settings(database_url="sqlite+pysqlite:///:memory:", internal_perception_token="test-token", admin_token="admin-token", llm_provider="fake", auto_create_schema=True)
    payload = {
        "expected_version": 0,
        "assistant_name": "项目助手",
        "welcome_message": "请提出现场问题。",
        "input_placeholder": "输入问题",
        "quick_questions": ["查看最新状态"],
        "show_evidence": False,
    }
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/v1/agent/ui-config").status_code == 404
        created = client.put("/api/v1/admin/agent/ui-config", json=payload, headers={"Authorization": "Bearer admin-token"})
        assert created.status_code == 200
        assert created.json()["version"] == 1
        assert client.get("/api/v1/agent/ui-config").json()["assistant_name"] == "项目助手"
        assert client.put("/api/v1/admin/agent/ui-config", json=payload, headers={"Authorization": "Bearer admin-token"}).status_code == 409
