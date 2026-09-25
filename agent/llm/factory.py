from __future__ import annotations

from agent.core.config import Settings
from .deepseek_adapter import DeepSeekChatModel
from .fake_adapter import FakeChatModel
from .protocol import ChatModelPort


def create_chat_model(settings: Settings) -> ChatModelPort:
    if settings.llm_provider == "fake":
        return FakeChatModel()
    if settings.llm_provider == "deepseek":
        return DeepSeekChatModel(
            api_key=settings.llm_api_key,
            model_name=settings.llm_model,
            base_url=settings.llm_base_url,
            timeout_seconds=settings.llm_timeout_seconds,
        )
    raise RuntimeError(f"Unsupported AGENT_LLM_PROVIDER: {settings.llm_provider}")
