from __future__ import annotations

from collections.abc import Sequence
from typing import Any, get_args

from agent.contracts.chat import ToolName
from agent.tools.base import AgentTool, Capability, ToolContext, describe_capability
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
            tools = _prune_tools_by_intent(tools, question, ctx)
        return [tool.to_catalog_entry(ctx) for tool in tools]

    def capability_summary(self, ctx: ToolContext) -> dict[str, Any]:
        """Build a data-driven runtime snapshot of enabled/disabled capabilities and tools."""
        active_caps = ctx.capabilities()
        notification_info = ctx.describe_notification_channels()

        capability_items: list[dict[str, Any]] = []
        for cap in Capability:
            label, disabled_reason = describe_capability(cap)
            entry: dict[str, Any] = {
                "capability": cap.value,
                "label": label,
                "enabled": cap in active_caps,
            }
            if cap not in active_caps:
                entry["reason"] = disabled_reason
            elif cap == Capability.NOTIFICATION and notification_info["labels"]:
                entry["active_channels"] = notification_info["labels"]
            capability_items.append(entry)

        enabled_tools: list[dict[str, str]] = []
        disabled_tools: list[dict[str, Any]] = []
        for tool in self._tools.values():
            if tool.requires <= active_caps:
                enabled_tools.append(tool.to_catalog_entry(ctx))
            else:
                missing = sorted((cap.value for cap in (tool.requires - active_caps)))
                reasons = [describe_capability(cap)[1] for cap in sorted(tool.requires - active_caps, key=lambda c: c.value)]
                disabled_tools.append({
                    "name": tool.name,
                    "description": tool.description,
                    "missing_capabilities": missing,
                    "reasons": reasons,
                })

        return {
            "capabilities": capability_items,
            "enabled_tools": enabled_tools,
            "disabled_tools": disabled_tools,
            "active_notification_channels": notification_info["labels"],
        }


def _prune_tools_by_intent(
    tools: list[AgentTool],
    question: str,
    ctx: ToolContext | None = None,
) -> list[AgentTool]:
    """Prune tools using each tool's cohesive intent metadata (OCP, no central keyword table)."""
    q = question.lower()
    filtered = [tool for tool in tools if tool.matches_intent(q, ctx)]
    return filtered if filtered else tools


DEFAULT_TOOL_CATALOG = ToolCatalog()
