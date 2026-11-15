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
    from agent.notifications.protocol import BriefingNotificationPort
    from agent.repositories.violations import ViolationRepository
    from agent.services.agent_write_actions import AgentWriteActionService
    from agent.services.knowledge_service import KnowledgeService
    from agent.services.learning_service import LearningService


class Capability(str, Enum):
    KNOWLEDGE = "knowledge"
    WRITE = "write"
    LEARNING = "learning"
    NOTIFICATION = "notification"


_CAPABILITY_METADATA: dict[Capability, tuple[str, str]] = {
    Capability.KNOWLEDGE: ("知识库与规范检索", "未启用或未配置知识库检索服务"),
    Capability.WRITE: ("运维写入待确认操作", "当前对话未开启写操作权限或服务未挂载"),
    Capability.LEARNING: ("安全报告与培训管理", "学习与报告服务未启用"),
    Capability.NOTIFICATION: ("群消息通知推送", "通知功能未开启或未配置有效推送通道（如 Webhook）"),
}


def describe_capability(cap: Capability) -> tuple[str, str]:
    """Return (display_label, disabled_reason) for a Capability."""
    return _CAPABILITY_METADATA.get(cap, (cap.value, f"{cap.value} 未启用"))


@dataclass
class ToolContext:
    repository: "ViolationRepository"
    knowledge_service: "KnowledgeService | None" = None
    write_action_service: "AgentWriteActionService | None" = None
    learning_service: "LearningService | None" = None
    notification_service: "BriefingNotificationPort | None" = None
    conversation_id: str | None = None
    model: Any = None
    extensions: dict[str, Any] = field(default_factory=dict)

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

    def describe_notification_channels(self) -> dict[str, Any]:
        """Return runtime metadata about configured notification channels."""
        from agent.notifications.protocol import describe_notification_channels

        return describe_notification_channels(self.notification_service)


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
    name: str
    description: str
    parameters: str
    handler: ToolHandler
    requires: frozenset[Capability] = frozenset()
    terminal_summary: Callable[[Any], str] | None = None
    intent_keywords: tuple[str, ...] = ()
    context_keywords: Callable[[ToolContext], tuple[str, ...]] | None = None
    description_resolver: Callable[[ToolContext], str] | None = None

    def execute(self, decision: ToolDecision, ctx: ToolContext) -> ToolOutcome:
        return self.handler(decision, ctx)

    def resolve_description(self, ctx: ToolContext | None = None) -> str:
        if ctx is not None and self.description_resolver is not None:
            resolved = self.description_resolver(ctx).strip()
            if resolved:
                return resolved
        return self.description

    def matches_intent(self, normalized_question: str, ctx: ToolContext | None = None) -> bool:
        """Return True when the normalized question matches this tool's declared intent keywords."""
        for kw in self.intent_keywords:
            if kw and kw.lower() in normalized_question:
                return True
        if ctx is not None and self.context_keywords is not None:
            for kw in self.context_keywords(ctx):
                if kw and kw.lower() in normalized_question:
                    return True
        # Allow dynamically registered custom tools without explicit intent_keywords
        # to match on normalized identifier tokens.
        name_token = self.name.replace("_", " ").lower()
        return bool(name_token and name_token in normalized_question)

    def to_catalog_entry(self, ctx: ToolContext | None = None) -> dict[str, str]:
        return {
            "name": self.name,
            "description": self.resolve_description(ctx),
            "parameters": self.parameters,
        }
