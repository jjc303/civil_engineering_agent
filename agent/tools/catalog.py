from __future__ import annotations

from collections.abc import Sequence
from typing import get_args

from agent.contracts.chat import ToolName
from agent.tools.base import AgentTool, ToolContext
from agent.tools.handlers import ALL_TOOLS


class ToolCatalog:
    """Declarative registry of all agent tools, verified against ToolName."""

    def __init__(self, tools: Sequence[AgentTool] = ALL_TOOLS, *, verify_exhaustive: bool = True) -> None:
        by_name: dict[ToolName, AgentTool] = {}
        for tool in tools:
            if tool.name in by_name:
                raise ValueError(f"duplicate tool registration: {tool.name}")
            by_name[tool.name] = tool
        if verify_exhaustive:
            expected = set(get_args(ToolName))
            registered = set(by_name)
            if registered != expected:
                missing = sorted(expected - registered)
                extra = sorted(registered - expected)
                raise RuntimeError(f"ToolCatalog mismatch with ToolName: missing={missing}, extra={extra}")
        self._tools = by_name

    def get(self, name: ToolName) -> AgentTool:
        try:
            return self._tools[name]
        except KeyError as exc:
            raise ValueError(f"unknown tool: {name}") from exc

    def available_tools(self, ctx: ToolContext) -> list[AgentTool]:
        caps = ctx.capabilities()
        return [tool for tool in self._tools.values() if tool.requires <= caps]

    def available_catalog(self, ctx: ToolContext) -> list[dict[str, str]]:
        return [tool.to_catalog_entry() for tool in self.available_tools(ctx)]


DEFAULT_TOOL_CATALOG = ToolCatalog()
