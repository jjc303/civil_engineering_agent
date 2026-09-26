from __future__ import annotations

from datetime import datetime
from pydantic import BaseModel, Field


class AssistantUiConfig(BaseModel):
    version: int
    assistant_name: str = Field(min_length=1, max_length=128)
    welcome_message: str = Field(min_length=1, max_length=4000)
    input_placeholder: str = Field(min_length=1, max_length=512)
    quick_questions: list[str] = Field(default_factory=list, max_length=12)
    show_evidence: bool = True
    updated_at_utc: datetime


class AssistantUiConfigUpdate(BaseModel):
    expected_version: int | None = Field(default=None, ge=0)
    assistant_name: str = Field(min_length=1, max_length=128)
    welcome_message: str = Field(min_length=1, max_length=4000)
    input_placeholder: str = Field(min_length=1, max_length=512)
    quick_questions: list[str] = Field(default_factory=list, max_length=12)
    show_evidence: bool = True
