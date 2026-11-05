from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from enum import Enum
from time import perf_counter
from typing import TYPE_CHECKING, Any

from agent.contracts.actions import GuidedSelection, PendingActionResponse
from agent.contracts.chat import Evidence, KnowledgeCitation, ToolDecision, ToolName, ToolResult, ToolTraceItem

if TYPE_CHECKING:
    from agent.graph.chat_state import ChatGraphState
    from agent.repositories.violations import ViolationRepository
    from agent.services.agent_write_actions import AgentWriteActionService
    from agent.services.knowledge_service import KnowledgeService
    from agent.services.learning_service import LearningService


class Capability(str, Enum):
    KNOWLEDGE = "knowledge"
    WRITE = "write"
    LEARNING = "learning"
    NOTIFICATION = "notification"


@dataclass
class ToolContext:
    repository: "ViolationRepository"
    knowledge_service: "KnowledgeService | None" = None
    write_action_service: "AgentWriteActionService | None" = None
    learning_service: "LearningService | None" = None
    notification_service: Any = None
    conversation_id: str | None = None
    model: Any = None

    def capabilities(self) -> frozenset[Capability]:
        active: set[Capability] = set()
        if self.knowledge_service is not None:
            active.add(Capability.KNOWLEDGE)
        if self.write_action_service is not None:
            active.add(Capability.WRITE)
        if self.learning_service is not None:
            active.add(Capability.LEARNING)
        if getattr(self.notification_service, "is_configured", False):
            active.add(Capability.NOTIFICATION)
        return frozenset(active)


def extract_evidence(data: object) -> list[Evidence]:
    if not isinstance(data, list):
        return []
    evidence: list[Evidence] = []
    for row in data:
        if not isinstance(row, dict) or "event_uuid" not in row or "occurred_at_utc" not in row:
            continue
        evidence.append(
            Evidence(
                event_uuid=row["event_uuid"],
                occurred_at_utc=row["occurred_at_utc"],
                snapshot_uri=row.get("snapshot_uri"),
            )
        )
    return evidence


@dataclass
class ToolOutcome:
    data: Any
    success: bool = True
    evidence: list[Evidence] = field(default_factory=list)
    citations: list[KnowledgeCitation] | None = None
    answer: str | None = None
    pending_action: PendingActionResponse | None = None
    guided_selection: GuidedSelection | None = None

    def to_state_update(
        self,
        state: "ChatGraphState",
        decision: ToolDecision,
        started_at: float,
    ) -> dict[str, Any]:
        duration_ms = int((perf_counter() - started_at) * 1000)
        result = ToolResult(tool_name=decision.tool_name, data=self.data)
        trace = ToolTraceItem(
            tool_name=decision.tool_name,
            success=self.success,
            purpose=decision.purpose,
            duration_ms=duration_ms,
        )
        base: dict[str, Any] = {
            "decision": None,
            "tool_results": [*state.get("tool_results", []), result],
            "tool_trace": [*state.get("tool_trace", []), trace],
        }
        if self.pending_action is not None:
            base["pending_action"] = self.pending_action
            base["knowledge_citations"] = []
            return base
        if self.guided_selection is not None:
            base["guided_selection"] = self.guided_selection
            base["knowledge_citations"] = []
            base["evidence"] = [*state.get("evidence", []), *self.evidence]
            return base
        if self.answer is not None:
            base["answer"] = self.answer
            base["knowledge_citations"] = []
            return base
        base["evidence"] = [*state.get("evidence", []), *self.evidence]
        if self.citations is not None:
            base["knowledge_citations"] = [*state.get("knowledge_citations", []), *self.citations]
        return base


ToolHandler = Callable[[ToolDecision, ToolContext], ToolOutcome]


@dataclass(frozen=True)
class AgentTool:
    name: ToolName
    description: str
    parameters: str
    handler: ToolHandler
    requires: frozenset[Capability] = frozenset()
    terminal_summary: Callable[[Any], str] | None = None

    def execute(self, decision: ToolDecision, ctx: ToolContext) -> ToolOutcome:
        return self.handler(decision, ctx)

    def to_catalog_entry(self) -> dict[str, str]:
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }
