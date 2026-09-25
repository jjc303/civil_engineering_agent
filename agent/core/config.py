from __future__ import annotations

from dataclasses import dataclass
import os


@dataclass(frozen=True)
class Settings:
    """Runtime settings loaded from environment variables."""

    database_url: str
    internal_perception_token: str
    tool_max_calls: int = 2
    auto_create_schema: bool = False

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(
            database_url=os.getenv("AGENT_DATABASE_URL", ""),
            tool_max_calls=int(os.getenv("AGENT_TOOL_MAX_CALLS", "2")),
            internal_perception_token=os.getenv("INTERNAL_PERCEPTION_TOKEN", ""),
            auto_create_schema=os.getenv("AGENT_AUTO_CREATE_SCHEMA", "false").lower() == "true",
        )

    def validate_for_runtime(self) -> None:
        if not self.database_url:
            raise RuntimeError("AGENT_DATABASE_URL must be configured")
        if not self.internal_perception_token:
            raise RuntimeError("INTERNAL_PERCEPTION_TOKEN must be configured")
        if not 1 <= self.tool_max_calls <= 2:
            raise RuntimeError("AGENT_TOOL_MAX_CALLS must be between 1 and 2")
