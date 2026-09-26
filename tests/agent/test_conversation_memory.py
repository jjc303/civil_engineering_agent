from fastapi.testclient import TestClient

from agent.core.config import Settings
from agent.db.models import ConversationSessionModel, ConversationTurnModel
from agent.main import create_app


def test_chat_persists_short_lived_memory_for_a_stable_conversation_id() -> None:
    settings = Settings(database_url="sqlite+pysqlite:///:memory:", internal_perception_token="test-token", llm_provider="fake", auto_create_schema=True)
    with TestClient(create_app(settings)) as client:
        response = client.post("/api/v1/agent/chat", json={"question": "查询最近违规", "conversation_id": "browser-session-1"})
        assert response.status_code == 200
        database = client.app.state.chat_service.database
        with database.session() as session:
            saved = session.get(ConversationSessionModel, "browser-session-1")
            assert saved is not None
            turns = list(session.query(ConversationTurnModel).filter_by(conversation_id="browser-session-1"))
            assert len(turns) == 1
            assert "reasoning" not in turns[0].verified_facts_json


def test_chat_without_conversation_id_remains_single_turn() -> None:
    settings = Settings(database_url="sqlite+pysqlite:///:memory:", internal_perception_token="test-token", llm_provider="fake", auto_create_schema=True)
    with TestClient(create_app(settings)) as client:
        assert client.post("/api/v1/agent/chat", json={"question": "查询最近违规"}).status_code == 200
        database = client.app.state.chat_service.database
        with database.session() as session:
            assert session.query(ConversationSessionModel).count() == 0
