from __future__ import annotations

import logging
from time import perf_counter
from typing import Literal

from langgraph.graph import END, START, StateGraph

from agent.contracts.actions import GuidedSelection, GuidedSelectionOption
from agent.contracts.chat import Evidence, KnowledgeCitation, ToolDecision, ToolResult, ToolTraceItem
from agent.contracts.event_v1 import EventStatus
from agent.contracts.query import ViolationQuery
from agent.db.models import ManagedCameraModel
from agent.llm.protocol import ChatModelPort
from agent.repositories.violations import ViolationRepository
from agent.tools.safety_tools import register_safety_tools
from .chat_state import ChatGraphState
from agent.services.knowledge_service import KnowledgeService
from agent.services.agent_write_actions import AgentWriteActionError, AgentWriteActionService

logger = logging.getLogger(__name__)


def build_chat_graph(repository: ViolationRepository, model: ChatModelPort, max_tool_calls: int = 2, knowledge_service: KnowledgeService | None = None, write_action_service: AgentWriteActionService | None = None):
    tools = register_safety_tools(repository)

    def select_tool(state: ChatGraphState) -> dict:
        previous = state.get("tool_results", [])
        if len(previous) >= max_tool_calls:
            return {"decision": None}
        try:
            catalog = tools.catalog()
            if knowledge_service:
                catalog.append({"name": "search_knowledge", "description": "检索当前有效的安全制度与方案资料。", "parameters": "knowledge_query: string, top_k: integer"})
            if write_action_service:
                catalog.extend([
                    {"name": "create_rectification_task", "description": "生成待确认的整改任务；必须给出违规事件 ID、标题、负责人和 UTC 截止时间。", "parameters": "violation_event_uuid, task_title, task_description, task_owner, task_due_at_utc"},
                    {"name": "update_rectification_task", "description": "生成待确认的整改任务更新；完成任务会把关联违规标为已解决。", "parameters": "task_id, task_owner, task_due_at_utc, task_status, task_note"},
                    {"name": "start_monitoring", "description": "生成待确认的摄像头监控启动操作。", "parameters": "camera_id"},
                    {"name": "stop_monitoring", "description": "生成待确认的摄像头监控停止操作。", "parameters": "camera_id"},
                    {"name": "list_rectification_targets", "description": "只读列出可创建整改任务的活动违规，供页面选择目标。", "parameters": "无"},
                    {"name": "list_monitoring_targets", "description": "只读列出可启停监控的已登记摄像头，供页面选择目标。", "parameters": "selection_action: start | stop"},
                ])
            return {"decision": model.decide(state["question"], previous, state.get("memory_context", ""), catalog)}
        except Exception:
            logger.exception("chat model failed to produce a validated tool decision")
            return {"error_code": "MODEL_DECISION_FAILED", "degraded": True}

    def next_after_selection(state: ChatGraphState) -> Literal["execute_tool", "respond", "fallback"]:
        if state.get("error_code"):
            return "fallback"
        return "execute_tool" if state.get("decision") else "respond"

    def execute_tool(state: ChatGraphState) -> dict:
        decision: ToolDecision = state["decision"]
        started_at = perf_counter()
        try:
            if decision.tool_name == "list_rectification_targets":
                events = repository.query_events(ViolationQuery(status=EventStatus.ACTIVE, limit=8))
                options = [GuidedSelectionOption(
                    option_id=event.event_uuid,
                    label=f"{event.violation_type} · {event.camera_id}",
                    description=f"{event.occurred_at_utc.strftime('%Y-%m-%d %H:%M UTC')} · {event.severity} · {event.event_uuid[:8]}",
                ) for event in events]
                selection = GuidedSelection(
                    kind="RECTIFICATION_TARGET",
                    prompt="请选择需要创建整改任务的活动违规；选中后填写整改要求、负责人和截止时间。" if options else "当前没有可创建整改任务的活动违规。",
                    options=options,
                )
                return _selection_response(state, decision, selection, [
                    Evidence(event_uuid=item.event_uuid, occurred_at_utc=item.occurred_at_utc, snapshot_uri=item.snapshot_uri) for item in events
                ], started_at)
            if decision.tool_name == "list_monitoring_targets":
                action = decision.selection_action
                assert action is not None
                cameras = list(repository.session.query(ManagedCameraModel).order_by(ManagedCameraModel.camera_id))
                verb = "停止" if action == "stop" else "启动"
                selection = GuidedSelection(
                    kind="CAMERA_TARGET",
                    prompt=f"请选择要{verb}监控的摄像头；选择后仍会显示确认卡片，不会立即执行。" if cameras else "当前没有已登记的摄像头可供操作。",
                    options=[GuidedSelectionOption(
                        option_id=camera.camera_id,
                        label=f"{camera.display_name}（{camera.camera_id}）",
                        description=f"当前期望状态：{camera.desired_state}",
                        follow_up_question=f"{verb} {camera.camera_id} 监控",
                    ) for camera in cameras],
                )
                return _selection_response(state, decision, selection, [], started_at)
            if decision.tool_name in {"create_rectification_task", "update_rectification_task", "start_monitoring", "stop_monitoring"}:
                if not write_action_service:
                    raise RuntimeError("write actions are disabled")
                pending = write_action_service.propose(state.get("conversation_id"), decision)
                result = ToolResult(tool_name=decision.tool_name, data=pending.model_dump(mode="json"))
                trace = ToolTraceItem(tool_name=decision.tool_name, success=True, purpose=decision.purpose, duration_ms=int((perf_counter() - started_at) * 1000))
                return {
                    "decision": None,
                    "pending_action": pending,
                    "tool_results": [*state.get("tool_results", []), result],
                    "tool_trace": [*state.get("tool_trace", []), trace],
                }
            if decision.tool_name == "get_camera_status":
                data = tools.invoke(decision.tool_name, camera_id=decision.camera_id)
            elif decision.tool_name == "get_all_camera_statuses":
                data = tools.invoke(decision.tool_name)
            elif decision.tool_name == "get_workforce_summary":
                data = tools.invoke(decision.tool_name)
            elif decision.tool_name == "get_current_weather":
                data = tools.invoke(decision.tool_name, location=decision.weather_location)
            elif decision.tool_name == "search_knowledge":
                if not knowledge_service:
                    raise RuntimeError("knowledge search is disabled")
                data, citations = knowledge_service.search(decision.knowledge_query or "", decision.top_k)
            else:
                data = tools.invoke(decision.tool_name, query=decision.query.model_dump(mode="json"))
            result = ToolResult(tool_name=decision.tool_name, data=data)
            trace = ToolTraceItem(tool_name=decision.tool_name, success=True, purpose=decision.purpose, duration_ms=int((perf_counter() - started_at) * 1000))
            response = {
                "decision": None,
                "tool_results": [*state.get("tool_results", []), result],
                "tool_trace": [*state.get("tool_trace", []), trace],
                "evidence": [*state.get("evidence", []), *_extract_evidence(data)],
            }
            if decision.tool_name == "search_knowledge":
                response["knowledge_citations"] = [*state.get("knowledge_citations", []), *citations]
            return response
        except AgentWriteActionError as exc:
            trace = ToolTraceItem(tool_name=decision.tool_name, success=False, purpose=decision.purpose, duration_ms=int((perf_counter() - started_at) * 1000))
            return {"decision": None, "tool_trace": [*state.get("tool_trace", []), trace], "answer": f"无法生成待确认操作：{exc}"}
        except Exception:
            logger.exception("chat tool execution failed: %s", decision.tool_name)
            trace = ToolTraceItem(tool_name=decision.tool_name, success=False, purpose=decision.purpose, duration_ms=int((perf_counter() - started_at) * 1000))
            return {"tool_trace": [*state.get("tool_trace", []), trace], "error_code": "TOOL_EXECUTION_FAILED", "degraded": True}

    def next_after_execution(state: ChatGraphState) -> Literal["select_tool", "respond", "fallback"]:
        if state.get("error_code"):
            return "fallback"
        if state.get("pending_action") or state.get("guided_selection") or state.get("answer"):
            return "respond"
        return "select_tool" if len(state.get("tool_results", [])) < max_tool_calls else "respond"

    def respond(state: ChatGraphState) -> dict:
        pending = state.get("pending_action")
        if pending:
            return {"answer": f"已生成待确认操作：{pending.summary}。请在下方确认后执行；确认有效期至 {pending.expires_at_utc.strftime('%H:%M')} UTC。"}
        selection = state.get("guided_selection")
        if selection:
            return {"answer": selection.prompt}
        if state.get("answer"):
            return {"answer": state["answer"]}
        try:
            return {"answer": model.respond(state["question"], state.get("tool_results", []), state.get("memory_context", ""))}
        except Exception:
            logger.exception("chat model failed to produce an answer")
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


def _selection_response(state: ChatGraphState, decision: ToolDecision, selection: GuidedSelection, evidence: list[Evidence], started_at: float) -> dict:
    trace = ToolTraceItem(tool_name=decision.tool_name, success=True, purpose=decision.purpose, duration_ms=int((perf_counter() - started_at) * 1000))
    result = ToolResult(tool_name=decision.tool_name, data=selection.model_dump(mode="json"))
    return {
        "decision": None,
        "guided_selection": selection,
        "tool_results": [*state.get("tool_results", []), result],
        "tool_trace": [*state.get("tool_trace", []), trace],
        "evidence": [*state.get("evidence", []), *evidence],
    }
