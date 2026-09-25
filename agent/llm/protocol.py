from __future__ import annotations

from typing import Protocol, Sequence

from agent.contracts.chat import ToolDecision, ToolResult


class ChatModelPort(Protocol):
    """Provider-neutral interface; adapters must never receive a DB session."""

    model_name: str

    def decide(self, question: str, previous_results: Sequence[ToolResult]) -> ToolDecision | None:
        """Return a validated tool decision, or None when enough facts are available."""

    def respond(self, question: str, results: Sequence[ToolResult]) -> str:
        """Create a user-facing answer only from the validated tool results."""
