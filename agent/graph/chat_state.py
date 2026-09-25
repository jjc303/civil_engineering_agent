from __future__ import annotations

from typing import TypedDict

from agent.contracts.chat import Evidence, ToolDecision, ToolResult, ToolTraceItem


class ChatGraphState(TypedDict, total=False):
    request_id: str
    question: str
    conversation_id: str | None
    decision: ToolDecision | None
    tool_results: list[ToolResult]
    tool_trace: list[ToolTraceItem]
    evidence: list[Evidence]
    answer: str
    error_code: str | None
    degraded: bool
