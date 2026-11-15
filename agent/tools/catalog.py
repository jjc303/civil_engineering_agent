from __future__ import annotations

from collections.abc import Sequence
from typing import get_args

from agent.contracts.chat import ToolName
from agent.tools.base import AgentTool, ToolContext
from agent.tools.handlers import ALL_TOOLS


class ToolCatalog:
    """Declarative registry of all agent tools, extensible at runtime (OCP)."""

    def __init__(self, tools: Sequence[AgentTool] = ALL_TOOLS, *, verify_exhaustive: bool = True) -> None:
        by_name: dict[str, AgentTool] = {}
        for tool in tools:
            if tool.name in by_name:
                raise ValueError(f"duplicate tool registration: {tool.name}")
            by_name[tool.name] = tool
        if verify_exhaustive:
            expected = set(get_args(ToolName))
            registered = set(by_name)
            missing = sorted(expected - registered)
            if missing:
                raise RuntimeError(f"ToolCatalog missing canonical ToolName tools: missing={missing}")
        self._tools = by_name

    def register(self, tool: AgentTool) -> None:
        """Register a new tool at runtime (OCP)."""
        self._tools[tool.name] = tool

    def with_tools(self, *tools: AgentTool) -> ToolCatalog:
        """Return a new ToolCatalog instance extended with additional tools."""
        combined = list(self._tools.values()) + list(tools)
        return ToolCatalog(combined, verify_exhaustive=False)

    def get(self, name: str) -> AgentTool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ValueError(f"unknown tool: {name}") from exc

    def available_tools(self, ctx: ToolContext) -> list[AgentTool]:
        caps = ctx.capabilities()
        return [tool for tool in self._tools.values() if tool.requires <= caps]

    def available_catalog(
        self,
        ctx: ToolContext,
        question: str | None = None,
        *,
        prune_by_intent: bool = False,
    ) -> list[dict[str, str]]:
        tools = self.available_tools(ctx)
        if prune_by_intent and question:
            tools = _prune_tools_by_intent(tools, question)
        return [tool.to_catalog_entry() for tool in tools]


_INTENT_TOOL_RULES: tuple[tuple[tuple[str, ...], frozenset[str]], ...] = (
    (
        ("天气", "气温", "下雨", "风力", "气象"),
        frozenset({"get_current_weather"}),
    ),
    (
        ("违规", "事件", "摄像头", "监控", "巡检", "人数", "画面", "离线", "在线"),
        frozenset({
            "query_violations",
            "get_violation_statistics",
            "get_camera_status",
            "get_all_camera_statuses",
            "get_workforce_summary",
            "list_monitoring_targets",
            "start_monitoring",
            "stop_monitoring",
        }),
    ),
    (
        ("规范", "标准", "规程", "条例", "案例", "事故", "查规", "文件", "条文"),
        frozenset({"search_knowledge", "list_standard_catalog"}),
    ),
    (
        ("报告", "周报", "培训", "学习", "答题", "考试", "建议", "教育"),
        frozenset({
            "get_learning_overview",
            "get_learning_insights",
            "list_safety_reports",
            "get_safety_report",
            "create_safety_report",
            "update_safety_report",
            "confirm_safety_report",
            "delete_safety_report",
            "list_training_tasks",
            "get_training_task",
            "get_training_statistics",
            "prepare_training_task",
            "create_training_task",
            "update_training_task",
            "publish_training_task",
            "delete_training_task",
        }),
    ),
    (
        ("整改", "工单", "闭环", "责任人", "截止时间"),
        frozenset({
            "create_rectification_task",
            "update_rectification_task",
            "list_rectification_targets",
        }),
    ),
    (
        ("飞书", "通知", "推送", "通报", "简报", "播报", "告警群", "发群"),
        frozenset({"send_feishu_notification"}),
    ),
)


def _prune_tools_by_intent(tools: list[AgentTool], question: str) -> list[AgentTool]:
    """Lightweight intent-based pruning to keep tool catalogue bounded."""
    q = question.lower()
    intent_tools: set[str] = set()
    for keywords, mapped_tools in _INTENT_TOOL_RULES:
        if any(keyword in q for keyword in keywords):
            intent_tools.update(mapped_tools)

    if not intent_tools:
        return tools

    filtered = [t for t in tools if t.name in intent_tools]
    return filtered if filtered else tools


DEFAULT_TOOL_CATALOG = ToolCatalog()
