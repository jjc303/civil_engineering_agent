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


def _prune_tools_by_intent(tools: list[AgentTool], question: str) -> list[AgentTool]:
    """Lightweight intent-based pruning to keep tool catalogue bounded."""
    q = question.lower()
    intent_tools: set[str] = set()

    is_weather = any(k in q for k in ("天气", "气温", "下雨", "风力", "气象"))
    is_cam_violation = any(k in q for k in ("违规", "事件", "摄像头", "监控", "巡检", "人数", "画面", "离线", "在线"))
    is_knowledge = any(k in q for k in ("规范", "标准", "规程", "条例", "案例", "事故", "查规", "文件", "条文"))
    is_learning_report = any(k in q for k in ("报告", "周报", "培训", "学习", "答题", "考试", "建议", "教育"))
    is_rectification = any(k in q for k in ("整改", "工单", "闭环", "责任人", "截止时间"))

    if is_weather:
        intent_tools.add("get_current_weather")
    if is_cam_violation:
        intent_tools.update({
            "query_violations",
            "get_violation_statistics",
            "get_camera_status",
            "get_all_camera_statuses",
            "get_workforce_summary",
            "list_monitoring_targets",
            "start_monitoring",
            "stop_monitoring",
        })
    if is_knowledge:
        intent_tools.update({"search_knowledge", "list_standard_catalog"})
    if is_learning_report:
        intent_tools.update({
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
        })
    if is_rectification:
        intent_tools.update({
            "create_rectification_task",
            "update_rectification_task",
            "list_rectification_targets",
        })

    if not intent_tools:
        return tools

    filtered = [t for t in tools if t.name in intent_tools]
    return filtered if filtered else tools


DEFAULT_TOOL_CATALOG = ToolCatalog()
