from __future__ import annotations

from collections.abc import Callable
from typing import TYPE_CHECKING

from .deepseek_adapter import DeepSeekChatModel
from .fake_adapter import FakeChatModel
from .protocol import ChatModelPort

if TYPE_CHECKING:
    from agent.core.config import Settings

ProviderBuilder = Callable[["Settings"], ChatModelPort]

_PROVIDERS: dict[str, ProviderBuilder] = {
    "fake": lambda _s: FakeChatModel(),
    "deepseek": lambda s: DeepSeekChatModel(
        api_key=s.llm_api_key,
        model_name=s.llm_model,
        base_url=s.llm_base_url,
        timeout_seconds=s.llm_timeout_seconds,
    ),
}


def register_chat_model_provider(name: str, builder: ProviderBuilder) -> None:
    _PROVIDERS[name.lower()] = builder


def supported_providers() -> frozenset[str]:
    return frozenset(_PROVIDERS)


def create_chat_model(settings: "Settings") -> ChatModelPort:
    builder = _PROVIDERS.get(settings.llm_provider)
    if builder is None:
        raise RuntimeError(f"Unsupported AGENT_LLM_PROVIDER: {settings.llm_provider}")
    return builder(settings)
