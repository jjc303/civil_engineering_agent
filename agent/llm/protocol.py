from __future__ import annotations

from typing import Any, Protocol, Sequence

from agent.contracts.chat import ToolDecision, ToolResult


class ChatModelPort(Protocol):
    """Provider-neutral interface; adapters must never receive a DB session."""

    model_name: str

    def decide(
        self,
        question: str,
        previous_results: Sequence[ToolResult],
        memory_context: str = "",
        tool_catalog: Sequence[dict[str, str]] = (),
        request_time_context: str = "",
    ) -> ToolDecision | None:
        """Return a validated tool decision, or None when enough facts are available."""

    def respond(
        self,
        question: str,
        results: Sequence[ToolResult],
        memory_context: str = "",
        tool_catalog: Sequence[dict[str, str]] = (),
        capability_status: dict[str, Any] | None = None,
        response_locale: str = "zh-CN",
        request_time_context: str = "",
    ) -> str:
        """Create a user-facing answer from validated tool results and runtime capability status."""

    def generate_structured(
        self,
        instruction: str,
        context: dict[str, Any],
        response_locale: str = "zh-CN",
    ) -> dict[str, Any]:
        """Generate a JSON object from bounded, server supplied evidence."""
