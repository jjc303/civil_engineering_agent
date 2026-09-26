from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from .query import ViolationQuery


ToolName = Literal["query_violations", "get_violation_statistics", "get_camera_status", "get_current_weather"]


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = Field(default=None, max_length=128)

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("question must not be blank")
        return value.strip()


class ToolDecision(BaseModel):
    """The only model output allowed to reach tool execution."""

    tool_name: ToolName
    query: ViolationQuery = Field(default_factory=lambda: ViolationQuery(limit=20))
    camera_id: str | None = Field(default=None, max_length=128)
    weather_location: str | None = Field(default=None, min_length=2, max_length=128)
    purpose: str = Field(min_length=1, max_length=256)

    @model_validator(mode="after")
    def enforce_tool_boundaries(self) -> "ToolDecision":
        if self.query.limit > 100:
            raise ValueError("chat tools may request at most 100 records")
        if self.query.start_time_utc and self.query.end_time_utc:
            if self.query.end_time_utc < self.query.start_time_utc:
                raise ValueError("end_time_utc must not precede start_time_utc")
            if (self.query.end_time_utc - self.query.start_time_utc).days > 31:
                raise ValueError("chat tool time range may not exceed 31 days")
        if self.tool_name == "get_camera_status" and not self.camera_id:
            raise ValueError("camera_id is required for get_camera_status")
        if self.tool_name == "get_current_weather" and not self.weather_location:
            raise ValueError("weather_location is required for get_current_weather")
        return self


class ToolTraceItem(BaseModel):
    tool_name: ToolName
    success: bool
    purpose: str
    duration_ms: int = Field(ge=0)


class Evidence(BaseModel):
    event_uuid: str
    occurred_at_utc: datetime
    snapshot_uri: str | None = None


class ChatResponse(BaseModel):
    request_id: str
    answer: str
    evidence: list[Evidence] = Field(default_factory=list)
    tool_trace: list[ToolTraceItem] = Field(default_factory=list)
    degraded: bool = False
    error_code: str | None = None


class ToolResult(BaseModel):
    tool_name: ToolName
    data: Any
    success: bool = True
