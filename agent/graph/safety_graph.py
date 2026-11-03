from __future__ import annotations

from langgraph.graph import END, START, StateGraph

from agent.contracts.chat import ToolDecision
from agent.contracts.query import ViolationQuery
from agent.graph.state import SafetyGraphState
from agent.repositories.violations import ViolationRepository
from agent.tools.base import ToolContext
from agent.tools.catalog import DEFAULT_TOOL_CATALOG


def build_safety_graph(repository: ViolationRepository):
    """Compile the deterministic v0.1 graph without an LLM provider dependency."""
    ctx = ToolContext(repository=repository)

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

    def execute_tool(state: SafetyGraphState) -> dict:
        tool_name = state["tool_name"]
        tool = DEFAULT_TOOL_CATALOG.get(tool_name)
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
