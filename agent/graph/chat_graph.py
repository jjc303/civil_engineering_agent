from __future__ import annotations

from time import perf_counter
from typing import Literal

from langgraph.graph import END, START, StateGraph

from agent.contracts.chat import Evidence, ToolDecision, ToolResult, ToolTraceItem
from agent.llm.protocol import ChatModelPort
from agent.repositories.violations import ViolationRepository
from agent.tools.safety_tools import register_safety_tools
from agent.tools.weather import extract_weather_location
from .chat_state import ChatGraphState


def build_chat_graph(repository: ViolationRepository, model: ChatModelPort, max_tool_calls: int = 2):
    tools = register_safety_tools(repository)

    def select_tool(state: ChatGraphState) -> dict:
        previous = state.get("tool_results", [])
        if len(previous) >= max_tool_calls:
            return {"decision": None}
        # Weather is an isolated public-data request.  Route it deterministically
        # before asking an LLM so a provider cannot accidentally query violations.
        if not previous and (location := extract_weather_location(state["question"])):
            return {"decision": ToolDecision(
                tool_name="get_current_weather",
                weather_location=location,
                purpose=f"查询 {location} 的当前天气",
            )}
        try:
            return {"decision": model.decide(state["question"], previous)}
        except Exception:
            return {"error_code": "MODEL_DECISION_FAILED", "degraded": True}

    def next_after_selection(state: ChatGraphState) -> Literal["execute_tool", "respond", "fallback"]:
        if state.get("error_code"):
            return "fallback"
        return "execute_tool" if state.get("decision") else "respond"

    def execute_tool(state: ChatGraphState) -> dict:
        decision: ToolDecision = state["decision"]
        started_at = perf_counter()
        try:
            if decision.tool_name == "get_camera_status":
                data = tools.invoke(decision.tool_name, camera_id=decision.camera_id)
            elif decision.tool_name == "get_current_weather":
                data = tools.invoke(decision.tool_name, location=decision.weather_location)
            else:
                data = tools.invoke(decision.tool_name, query=decision.query.model_dump(mode="json"))
            result = ToolResult(tool_name=decision.tool_name, data=data)
            trace = ToolTraceItem(tool_name=decision.tool_name, success=True, purpose=decision.purpose, duration_ms=int((perf_counter() - started_at) * 1000))
            return {
                "decision": None,
                "tool_results": [*state.get("tool_results", []), result],
                "tool_trace": [*state.get("tool_trace", []), trace],
                "evidence": [*state.get("evidence", []), *_extract_evidence(data)],
            }
        except Exception:
            trace = ToolTraceItem(tool_name=decision.tool_name, success=False, purpose=decision.purpose, duration_ms=int((perf_counter() - started_at) * 1000))
            return {"tool_trace": [*state.get("tool_trace", []), trace], "error_code": "TOOL_EXECUTION_FAILED", "degraded": True}

    def next_after_execution(state: ChatGraphState) -> Literal["select_tool", "respond", "fallback"]:
        if state.get("error_code"):
            return "fallback"
        return "select_tool" if len(state.get("tool_results", [])) < max_tool_calls else "respond"

    def respond(state: ChatGraphState) -> dict:
        try:
            return {"answer": model.respond(state["question"], state.get("tool_results", []))}
        except Exception:
            return {"answer": "安全问答服务暂时不可用，请稍后重试。", "error_code": "MODEL_RESPONSE_FAILED", "degraded": True}

    def fallback(_: ChatGraphState) -> dict:
        return {"answer": "安全数据服务暂时不可用，请稍后重试。", "degraded": True}

    graph = StateGraph(ChatGraphState)
    graph.add_node("select_tool", select_tool)
    graph.add_node("execute_tool", execute_tool)
    graph.add_node("respond", respond)
    graph.add_node("fallback", fallback)
    graph.add_edge(START, "select_tool")
    graph.add_conditional_edges("select_tool", next_after_selection)
    graph.add_conditional_edges("execute_tool", next_after_execution)
    graph.add_edge("respond", END)
    graph.add_edge("fallback", END)
    return graph.compile()


def _extract_evidence(data: object) -> list[Evidence]:
    if not isinstance(data, list):
        return []
    evidence: list[Evidence] = []
    for row in data:
        if not isinstance(row, dict) or "event_uuid" not in row or "occurred_at_utc" not in row:
            continue
        evidence.append(Evidence(event_uuid=row["event_uuid"], occurred_at_utc=row["occurred_at_utc"], snapshot_uri=row.get("snapshot_uri")))
    return evidence
