import pytest

from agent.core.config import Settings
from agent.llm.deepseek_adapter import DeepSeekChatModel
from agent.llm.factory import create_chat_model
from agent.llm.fake_adapter import FakeChatModel


def test_default_provider_remains_fake_for_local_and_ci() -> None:
    settings = Settings(database_url="sqlite+pysqlite:///:memory:", internal_perception_token="test")
    settings.validate_for_runtime()
    assert isinstance(create_chat_model(settings), FakeChatModel)


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
        llm_provider="deepseek",
    )
    with pytest.raises(RuntimeError, match="AGENT_LLM_API_KEY"):
        settings.validate_for_runtime()
