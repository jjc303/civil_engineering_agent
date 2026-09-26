from __future__ import annotations

from dataclasses import dataclass
import os
from dotenv import load_dotenv


# Local .env values fill missing variables; deployed environment values always win.
load_dotenv(override=False)

@dataclass(frozen=True)
class Settings:
    """Runtime settings loaded from environment variables."""

    database_url: str
    internal_perception_token: str
    tool_max_calls: int = 2
    auto_create_schema: bool = False
    llm_provider: str = "deepseek"
    llm_model: str = "deepseek-flash"
    llm_base_url: str = "https://api.deepseek.com"
    llm_api_key: str = ""
    llm_timeout_seconds: float = 20.0
    media_root: str = "./runs/media"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            llm_provider=os.getenv("AGENT_LLM_PROVIDER", "deepseek").lower(),
            llm_model=os.getenv("AGENT_LLM_MODEL", "deepseek-flash"),
            llm_base_url=os.getenv("AGENT_LLM_BASE_URL", "https://api.deepseek.com"),
            llm_api_key=os.getenv("AGENT_LLM_API_KEY", ""),
            llm_timeout_seconds=float(os.getenv("AGENT_LLM_TIMEOUT_SECONDS", "20")),
            database_url=os.getenv("AGENT_DATABASE_URL", ""),
            tool_max_calls=int(os.getenv("AGENT_TOOL_MAX_CALLS", "2")),
            internal_perception_token=os.getenv("INTERNAL_PERCEPTION_TOKEN", ""),
            auto_create_schema=os.getenv("AGENT_AUTO_CREATE_SCHEMA", "false").lower() == "true",
            media_root=os.getenv("AGENT_MEDIA_ROOT", "./runs/media"),
        )

    def validate_for_runtime(self) -> None:
        if not self.database_url:
            raise RuntimeError("AGENT_DATABASE_URL must be configured")
        if not self.internal_perception_token:
            raise RuntimeError("INTERNAL_PERCEPTION_TOKEN must be configured")
        if not 1 <= self.tool_max_calls <= 2:
            raise RuntimeError("AGENT_TOOL_MAX_CALLS must be between 1 and 2")
        if self.llm_provider not in {"fake", "deepseek"}:
            raise RuntimeError("AGENT_LLM_PROVIDER must be fake or deepseek")
        if self.llm_provider == "deepseek" and not self.llm_api_key:
            raise RuntimeError("AGENT_LLM_API_KEY must be configured for DeepSeek")
        if self.llm_timeout_seconds <= 0:
            raise RuntimeError("AGENT_LLM_TIMEOUT_SECONDS must be positive")
