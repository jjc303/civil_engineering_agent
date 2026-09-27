from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field


PendingActionType = Literal[
    "create_rectification_task",
    "update_rectification_task",
    "start_monitoring",
    "stop_monitoring",
]
PendingActionStatus = Literal["PENDING", "EXECUTING", "EXECUTED", "CANCELLED", "EXPIRED", "FAILED"]


class PendingActionResponse(BaseModel):
    """A server-stored operation that still needs an explicit UI confirmation."""

    confirmation_id: str
    action_type: PendingActionType
    summary: str
    expires_at_utc: datetime
    status: PendingActionStatus = "PENDING"


class ActionConfirmationRequest(BaseModel):
    conversation_id: str = Field(min_length=1, max_length=128)


class ActionExecutionResponse(BaseModel):
    confirmation_id: str
    action_type: PendingActionType
    status: PendingActionStatus
    summary: str
    result: dict[str, Any] = Field(default_factory=dict)
    idempotent: bool = False


class GuidedSelectionOption(BaseModel):
    option_id: str
    label: str
    description: str
    follow_up_question: str | None = None


class GuidedSelection(BaseModel):
    """Safe, read-only choices presented when a write target is ambiguous."""

    kind: Literal["RECTIFICATION_TARGET", "CAMERA_TARGET"]
    prompt: str
    options: list[GuidedSelectionOption] = Field(default_factory=list)
