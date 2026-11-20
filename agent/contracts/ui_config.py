from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class MascotProfile(BaseModel):
    """Configurable server-driven profile for the site-wide floating IP agent."""

    enabled: bool = True
    persona_name: str = Field(default="安小盾", min_length=1, max_length=64)
    idle_greeting: str = Field(
        default="我是施工安全卫士安小盾，随时为您巡检风险与解答规范。",
        min_length=1,
        max_length=256,
    )
    alert_reaction_enabled: bool = True
    voice_enabled_by_default: bool = False


class AssistantUiConfig(BaseModel):
    version: int
    assistant_name: str = Field(min_length=1, max_length=128)
    welcome_message: str = Field(min_length=1, max_length=4000)
    input_placeholder: str = Field(min_length=1, max_length=512)
    quick_questions: list[str] = Field(default_factory=list, max_length=12)
    show_evidence: bool = True
    mascot_profile: MascotProfile = Field(default_factory=MascotProfile)
    updated_at_utc: datetime


class AssistantUiConfigUpdate(BaseModel):
    expected_version: int | None = Field(default=None, ge=0)
    assistant_name: str = Field(min_length=1, max_length=128)
    welcome_message: str = Field(min_length=1, max_length=4000)
    input_placeholder: str = Field(min_length=1, max_length=512)
    quick_questions: list[str] = Field(default_factory=list, max_length=12)
    show_evidence: bool = True
