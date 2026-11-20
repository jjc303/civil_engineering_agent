from __future__ import annotations

from collections.abc import Sequence
from dataclasses import replace
import inspect
import logging
from time import perf_counter
from typing import Any, Literal

from langchain_core.runnables import RunnableConfig
from langgraph.graph import END, START, StateGraph

from agent.contracts.chat import ToolDecision, ToolResult, ToolTraceItem
from agent.domain.standards_guard import (
    CHAT_STANDARD_REFERENCE_RE as _STANDARD_REFERENCE,
    contains_unsupported_standard_reference as _contains_unsupported_standard_reference,
)
from agent.core.config import DEFAULT_RAG_TOP_K, DEFAULT_TOOL_MAX_CALLS
from agent.llm.protocol import ChatModelPort
from agent.prompts.chat_messages import (
    DATA_SERVICE_UNAVAILABLE_ANSWER,
    MODEL_RESPONSE_FAILED_ANSWER,
    PENDING_ACTION_ANSWER_TEMPLATE,
    PROMPT_STANDARDS_HEADER,
    UNSUPPORTED_STANDARD_ANSWER,
    WRITE_ACTION_PROPOSE_FAILED_TEMPLATE,
)
from agent.repositories.violations import ViolationRepository
from agent.services.agent_write_actions import AgentWriteActionError, AgentWriteActionService
from agent.services.knowledge_service import KnowledgeService
from agent.services.learning_service import LearningService
from agent.services.standards_context import build_standards_context
from agent.tools.base import ToolContext
from agent.tools.catalog import DEFAULT_TOOL_CATALOG, ToolCatalog
from .chat_state import ChatGraphState

logger = logging.getLogger(__name__)


def _emit_stage(
    ctx: ToolContext | None,
    stage: str,
    tool_name: str | None = None,
    purpose: str | None = None,
) -> None:
    if ctx is None:
        return
    callback = ctx.extensions.get("stage_callback")
    if callable(callback):
        try:
            callback(stage, tool_name, purpose)
        except Exception:
            logger.debug("Ignoring stage callback failure for stage=%s", stage, exc_info=True)


def _resolve_context(
    state: ChatGraphState,
    config: RunnableConfig | None,
    default_context: ToolContext | None,
) -> ToolContext:
    ctx: ToolContext | None = None
    if config:
        ctx = config.get("configurable", {}).get("tool_context")
    ctx = ctx or default_context
    if ctx is None:
        raise RuntimeError("ToolContext must be provided via config['configurable']['tool_context'] or default_context")
    if ctx.conversation_id is None and state.get("conversation_id") is not None:
        ctx = replace(ctx, conversation_id=state.get("conversation_id"))
    return ctx


def _invoke_model_respond(
    active_model: ChatModelPort,
    question: str,
    tool_results: Sequence[ToolResult],
    prompt_context: str,
    tool_catalog: Sequence[dict[str, str]],
    capability_status: dict[str, Any],
    response_locale: str = "zh-CN",
) -> str:
    """Invoke model.respond while keeping backwards compatibility with 3-arg stubs."""
    try:
        params = inspect.signature(active_model.respond).parameters.values()
        accepts_var_kw = any(p.kind == inspect.Parameter.VAR_KEYWORD for p in params)
        param_names = {p.name for p in params}
    except (TypeError, ValueError):
        accepts_var_kw = False
        param_names = set()

    kwargs: dict[str, Any] = {}
    if accepts_var_kw or "tool_catalog" in param_names:
        kwargs["tool_catalog"] = tool_catalog
    if accepts_var_kw or "capability_status" in param_names:
        kwargs["capability_status"] = capability_status
    if accepts_var_kw or "response_locale" in param_names:
        kwargs["response_locale"] = response_locale
    return active_model.respond(question, tool_results, prompt_context, **kwargs)


def build_compiled_chat_graph(
    model: ChatModelPort,
    max_tool_calls: int = DEFAULT_TOOL_MAX_CALLS,
    catalog: ToolCatalog = DEFAULT_TOOL_CATALOG,
    default_context: ToolContext | None = None,
):
    def select_tool(state: ChatGraphState, config: RunnableConfig) -> dict[str, Any]:
        previous = state.get("tool_results", [])
        if len(previous) >= max_tool_calls:
            return {"decision": None}
        try:
            ctx = _resolve_context(state, config, default_context)
            _emit_stage(ctx, "selecting_tool")
            active_model = ctx.model or model
            tool_catalog = catalog.available_catalog(
                ctx,
                question=state.get("question"),
                prune_by_intent=bool(ctx.extensions.get("prune_by_intent", False)),
            )
            return {"decision": active_model.decide(state["question"], previous, state.get("memory_context", ""), tool_catalog)}
        except Exception:
            logger.exception("chat model failed to produce a validated tool decision")
            return {"error_code": "MODEL_DECISION_FAILED", "degraded": True}

    def next_after_selection(state: ChatGraphState) -> Literal["execute_tool", "respond", "fallback"]:
        if state.get("error_code"):
            return "fallback"
        return "execute_tool" if state.get("decision") else "respond"

    def execute_tool(state: ChatGraphState, config: RunnableConfig) -> dict[str, Any]:
        decision_raw = state["decision"]
        decisions = decision_raw if isinstance(decision_raw, list) else [decision_raw]
        current_state = dict(state)

        for dec in decisions:
            started_at = perf_counter()
            try:
                ctx = _resolve_context(current_state, config, default_context)
                _emit_stage(ctx, "executing_tool", dec.tool_name, dec.purpose)
                tool = catalog.get(dec.tool_name)
                outcome = tool.execute(dec, ctx)
                update = outcome.to_state_update(current_state, dec, started_at)
                current_state.update(update)
                if current_state.get("pending_action") or current_state.get("guided_selection") or current_state.get("answer"):
                    break
            except AgentWriteActionError as exc:
                trace = ToolTraceItem(
                    tool_name=dec.tool_name,
                    success=False,
                    purpose=dec.purpose,
                    duration_ms=int((perf_counter() - started_at) * 1000),
                )
                current_state["decision"] = None
                current_state["tool_trace"] = [*current_state.get("tool_trace", []), trace]
                current_state["answer"] = WRITE_ACTION_PROPOSE_FAILED_TEMPLATE.format(reason=exc)
                break
            except Exception:
                logger.exception("chat tool execution failed: %s", dec.tool_name)
                trace = ToolTraceItem(
                    tool_name=dec.tool_name,
                    success=False,
                    purpose=dec.purpose,
                    duration_ms=int((perf_counter() - started_at) * 1000),
                )
                current_state["tool_trace"] = [*current_state.get("tool_trace", []), trace]
                current_state["error_code"] = "TOOL_EXECUTION_FAILED"
                current_state["degraded"] = True
                break

        current_state["decision"] = None
        return current_state

    def next_after_execution(state: ChatGraphState) -> Literal["select_tool", "respond", "fallback"]:
        if state.get("error_code"):
            return "fallback"
        if state.get("pending_action") or state.get("guided_selection") or state.get("answer"):
            return "respond"
        return "select_tool" if len(state.get("tool_results", [])) < max_tool_calls else "respond"

    def respond(state: ChatGraphState, config: RunnableConfig) -> dict[str, Any]:
        pending = state.get("pending_action")
        if pending:
            return {
                "answer": PENDING_ACTION_ANSWER_TEMPLATE.format(
                    summary=pending.summary,
                    expires_at=pending.expires_at_utc.strftime("%H:%M"),
                )
            }
        selection = state.get("guided_selection")
        if selection:
            return {"answer": selection.prompt}
        if state.get("answer"):
            return {"answer": state["answer"]}
        tool_results = state.get("tool_results", [])
        if tool_results:
            last_tool_name = tool_results[-1].tool_name
            if all(item.tool_name == last_tool_name for item in tool_results):
                tool_spec = catalog.get(last_tool_name)
                if tool_spec.terminal_summary is not None:
                    return {
                        "answer": tool_spec.terminal_summary(tool_results[-1].data),
                        "knowledge_citations": [],
                    }
        try:
            ctx = _resolve_context(state, config, default_context)
            _emit_stage(ctx, "responding")
            active_model = ctx.model or model

            standards_context = state.get("standards_context")
            knowledge_citations = list(state.get("knowledge_citations", []))
            if standards_context is None:
                top_k = int(ctx.extensions.get("standards_top_k", DEFAULT_RAG_TOP_K))
                standards_result = build_standards_context(
                    ctx.knowledge_service,
                    state["question"],
                    top_k,
                    failure_log_message="On-demand standards retrieval failed",
                )
                standards_context = standards_result.context_text
                knowledge_citations.extend(standards_result.citations)

            prompt_context = (
                state.get("memory_context", "")
                + state.get("page_context_text", "")
                + PROMPT_STANDARDS_HEADER
                + standards_context
            )
            full_catalog = catalog.available_catalog(ctx, prune_by_intent=False)
            capability_status = catalog.capability_summary(ctx)
            answer = _invoke_model_respond(
                active_model,
                state["question"],
                tool_results,
                prompt_context,
                full_catalog,
                capability_status,
                response_locale=state.get("response_locale", "zh-CN"),
            )
            if _contains_unsupported_standard_reference(answer, standards_context):
                return {
                    "answer": UNSUPPORTED_STANDARD_ANSWER,
                    "knowledge_citations": [],
                    "degraded": True,
                    "error_code": "UNSUPPORTED_STANDARD_REFERENCE",
                }
            return {"answer": answer, "knowledge_citations": knowledge_citations}
        except Exception:
            logger.exception("chat model failed to produce an answer")
            return {"answer": MODEL_RESPONSE_FAILED_ANSWER, "error_code": "MODEL_RESPONSE_FAILED", "degraded": True}

    def fallback(_: ChatGraphState) -> dict[str, Any]:
        return {"answer": DATA_SERVICE_UNAVAILABLE_ANSWER, "degraded": True}

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


def build_chat_graph(
    repository: ViolationRepository,
    model: ChatModelPort,
    max_tool_calls: int = DEFAULT_TOOL_MAX_CALLS,
    knowledge_service: KnowledgeService | None = None,
    write_action_service: AgentWriteActionService | None = None,
    learning_service: LearningService | None = None,
    notification_service: object | None = None,
):
    default_context = ToolContext(
        repository=repository,
        knowledge_service=knowledge_service,
        write_action_service=write_action_service,
        learning_service=learning_service,
        notification_service=notification_service,
    )
    return build_compiled_chat_graph(model=model, max_tool_calls=max_tool_calls, default_context=default_context)
