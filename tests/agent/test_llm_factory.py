import pytest

from agent.core.config import Settings
from agent.llm.deepseek_adapter import DeepSeekChatModel
from agent.llm.factory import create_chat_model
from agent.llm.fake_adapter import FakeChatModel


def test_default_provider_is_deepseek() -> None:
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        internal_perception_token="test",
        llm_api_key="test-key-not-used-for-network",
    )
    settings.validate_for_runtime()
    assert isinstance(create_chat_model(settings), DeepSeekChatModel)


def test_environment_default_provider_is_deepseek(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("AGENT_DATABASE_URL", "sqlite+pysqlite:///:memory:")
    monkeypatch.setenv("INTERNAL_PERCEPTION_TOKEN", "test")
    monkeypatch.setenv("AGENT_LLM_API_KEY", "test-key-not-used-for-network")
    monkeypatch.delenv("AGENT_LLM_PROVIDER", raising=False)

    settings = Settings.from_env()

    assert settings.llm_provider == "deepseek"


def test_deepseek_provider_is_constructed_without_a_network_call() -> None:
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        internal_perception_token="test",
        llm_provider="deepseek",
        llm_api_key="test-key-not-used-for-network",
        llm_model="deepseek-flash",
    )
    settings.validate_for_runtime()
    model = create_chat_model(settings)
    assert isinstance(model, DeepSeekChatModel)
    assert model.model_name == "deepseek-flash"


def test_deepseek_requires_an_api_key() -> None:
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        internal_perception_token="test",
    )
    with pytest.raises(RuntimeError, match="AGENT_LLM_API_KEY"):
        settings.validate_for_runtime()


def test_fake_provider_remains_available_for_offline_tests() -> None:
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        internal_perception_token="test",
        llm_provider="fake",
    )
    settings.validate_for_runtime()
    assert isinstance(create_chat_model(settings), FakeChatModel)
