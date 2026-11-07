from __future__ import annotations

from typing import Any
from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from agent.contracts.chat import ToolDecision
from agent.contracts.query import ViolationQuery
from agent.graph.state import SafetyGraphState
from agent.repositories.violations import ViolationRepository
from agent.tools.base import ToolContext
from agent.tools.catalog import DEFAULT_TOOL_CATALOG, ToolCatalog


def _resolve_context(
    config: RunnableConfig | None,
    default_context: ToolContext | None,
) -> ToolContext:
    ctx = None
    if config:
        ctx = config.get("configurable", {}).get("tool_context")
    ctx = ctx or default_context
    if ctx is None:
        raise RuntimeError("ToolContext must be provided via config['configurable']['tool_context'] or default_context")
    return ctx


def build_compiled_safety_graph(
    catalog: ToolCatalog = DEFAULT_TOOL_CATALOG,
    default_context: ToolContext | None = None,
):
    """Compile the deterministic safety StateGraph once for high-throughput reuse."""

    def select_tool(state: SafetyGraphState) -> dict:
        mapping = {
            "violations": "query_violations",
            "statistics": "get_violation_statistics",
            "camera_status": "get_camera_status",
        }
        operation = state["operation"]
        if operation not in mapping:
            raise ValueError(f"unsupported operation: {operation}")
        return {"tool_name": mapping[operation]}

    def execute_tool(state: SafetyGraphState, config: RunnableConfig) -> dict:
        tool_name = state["tool_name"]
        tool = catalog.get(tool_name)
        ctx = _resolve_context(config, default_context)
        decision = ToolDecision.model_construct(
            tool_name=tool_name,
            camera_id=state.get("camera_id"),
            query=ViolationQuery.model_validate(state.get("query", {})),
            purpose="deterministic safety graph query",
        )
        outcome = tool.execute(decision, ctx)
        return {"result": outcome.data}

    def format_response(state: SafetyGraphState) -> dict:
        payload = state["result"]
        if state["operation"] == "statistics":
            summary = f"统计到 {payload['total_violations']} 条违规事件。"
        elif state["operation"] == "violations":
            summary = f"查询到 {len(payload)} 条违规事件。"
        else:
            summary = "摄像头状态已返回。" if payload else "未找到该摄像头状态。"
        return {"summary": summary}

    graph = StateGraph(SafetyGraphState)
    graph.add_node("select_tool", select_tool)
    graph.add_node("execute_tool", execute_tool)
    graph.add_node("format_response", format_response)
    graph.add_edge(START, "select_tool")
    graph.add_edge("select_tool", "execute_tool")
    graph.add_edge("execute_tool", "format_response")
    graph.add_edge("format_response", END)
    return graph.compile()


COMPILED_SAFETY_GRAPH = build_compiled_safety_graph()


def build_safety_graph(repository: ViolationRepository):
    """Compile the deterministic v0.1 graph with an embedded default context (backward compatibility)."""
    return build_compiled_safety_graph(default_context=ToolContext(repository=repository))

