from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator, Callable
import logging
from typing import Any
from uuid import uuid4

from agent.contracts.chat import (
    ChatRequest,
    ChatResponse,
    ChatStreamEvent,
    ChatStreamStage,
    KnowledgeCitation,
    PageContext,
    ReportPreview,
    ToolResult,
    TrainingPreview,
)
from agent.core.config import DEFAULT_RAG_TOP_K, DEFAULT_TOOL_MAX_CALLS
from agent.db.base import Database
from agent.graph.chat_graph import build_compiled_chat_graph
from agent.i18n import DEFAULT_LOCALE, SupportedLocale, localize_response, to_simplified_text
from agent.llm.protocol import ChatModelPort
from agent.notifications.protocol import BriefingNotificationPort
from agent.prompts.chat_messages import DEFAULT_UNAVAILABLE_ANSWER, PROMPT_PAGE_CONTEXT_HEADER
from agent.repositories.violations import ViolationRepository
from agent.services.agent_write_actions import AgentWriteActionService
from agent.services.conversation_memory import ConversationMemory
from agent.services.knowledge_service import KnowledgeService
from agent.services.learning_service import LearningService
from agent.services.standards_context import build_standards_context
from agent.tools.base import ToolContext

logger = logging.getLogger(__name__)

StageCallback = Callable[[ChatStreamStage, str | None, str | None], None]


def _sanitize_context_value(value: str | None, max_len: int = 128) -> str | None:
    if not value:
        return None
    cleaned = " ".join(value.replace("\r", " ").replace("\n", " ").split())
    return cleaned[:max_len] if cleaned else None


def format_page_context(page_context: PageContext | None) -> str:
    """Serialize sanitized frontend route/selection hints for model disambiguation."""
    if page_context is None:
        return ""
    fields: list[str] = []
    route_title = _sanitize_context_value(page_context.route_title)
    route_key = _sanitize_context_value(page_context.route_key, 64)
    camera_id = _sanitize_context_value(page_context.camera_id)
    event_uuid = _sanitize_context_value(page_context.event_uuid, 64)
    if route_title or route_key:
        fields.append(f"当前页面：{route_title or route_key} ({route_key or '-'})")
    if camera_id:
        fields.append(f"焦点摄像头：{camera_id}")
    if event_uuid:
        fields.append(f"焦点违规事件：{event_uuid}")
    if not fields:
        return ""
    return PROMPT_PAGE_CONTEXT_HEADER + "；".join(fields)


class ChatService:
    def __init__(
        self,
        database: Database,
        model: ChatModelPort,
        max_tool_calls: int = DEFAULT_TOOL_MAX_CALLS,
        memory_enabled: bool = True,
        memory_ttl_hours: int = 24,
        memory_recent_turns: int = 6,
        knowledge_service: KnowledgeService | None = None,
        write_action_service: AgentWriteActionService | None = None,
        standards_top_k: int = DEFAULT_RAG_TOP_K,
        learning_service: LearningService | None = None,
        notification_service: BriefingNotificationPort | None = None,
        standards_on_demand: bool = False,
    ):
        self.database = database
        self.model = model
        self.max_tool_calls = max_tool_calls
        self.memory_enabled, self.memory_ttl_hours, self.memory_recent_turns = (
            memory_enabled,
            memory_ttl_hours,
            memory_recent_turns,
        )
        self.knowledge_service = knowledge_service
        self.write_action_service = write_action_service
        self.standards_top_k = standards_top_k
        self.learning_service = learning_service
        self.notification_service = notification_service
        self.standards_on_demand = standards_on_demand
        self._graph = build_compiled_chat_graph(self.model, self.max_tool_calls)

    def _build_standards_context(self, question: str) -> tuple[str, list[KnowledgeCitation], str | None]:
        result = build_standards_context(
            self.knowledge_service,
            question,
            self.standards_top_k,
            failure_log_message="Automatic standards retrieval failed",
        )
        return result.context_text, result.citations, result.error_code

    def _run_chat_pipeline(
        self,
        request: ChatRequest,
        *,
        locale: SupportedLocale = DEFAULT_LOCALE,
        stage_callback: StageCallback | None = None,
    ) -> ChatResponse:
        request_id = str(uuid4())
        page_context_text = format_page_context(request.page_context)
        with self.database.session() as session:
            memory = ConversationMemory(session, self.memory_ttl_hours, self.memory_recent_turns)
            if self.memory_enabled:
                memory.cleanup_expired()
            context = memory.load_context(request.conversation_id) if self.memory_enabled else ""
            if self.standards_on_demand:
                standards_context = None
                standard_citations: list[KnowledgeCitation] = []
                standards_error = None
            else:
                if stage_callback is not None:
                    stage_callback("retrieving_standards", None, None)
                standards_context, standard_citations, standards_error = self._build_standards_context(
                    request.question
                )
            extensions: dict[str, Any] = {"standards_top_k": self.standards_top_k}
            if stage_callback is not None:
                extensions["stage_callback"] = stage_callback
            tool_context = ToolContext(
                repository=ViolationRepository(session),
                knowledge_service=self.knowledge_service,
                write_action_service=self.write_action_service,
                learning_service=self.learning_service,
                notification_service=self.notification_service,
                conversation_id=request.conversation_id,
                model=self.model,
                extensions=extensions,
            )
            output = self._graph.invoke(
                {
                    "request_id": request_id,
                    "question": request.question,
                    "conversation_id": request.conversation_id,
                    "response_locale": locale,
                    "tool_results": [],
                    "tool_trace": [],
                    "evidence": [],
                    "knowledge_citations": standard_citations,
                    "memory_context": context,
                    "page_context_text": page_context_text,
                    "standards_context": standards_context,
                    "degraded": False,
                },
                config={"configurable": {"tool_context": tool_context}},
            )
            if standards_error:
                output["degraded"] = True
                output["error_code"] = output.get("error_code") or standards_error
            if self.memory_enabled:
                try:
                    memory.persist(
                        request.conversation_id,
                        to_simplified_text(request.question),
                        to_simplified_text(output.get("answer", "")),
                        output.get("tool_results", []),
                        output.get("tool_trace", []),
                        output.get("knowledge_citations", []),
                    )
                except Exception:
                    output["degraded"] = True
                    output["error_code"] = output.get("error_code") or "MEMORY_PERSIST_FAILED"
        report_previews, report_count = _report_previews(output.get("tool_results", []))
        training_previews, training_count = _training_previews(output.get("tool_results", []))
        response = ChatResponse(
            request_id=request_id,
            answer=output.get("answer", DEFAULT_UNAVAILABLE_ANSWER),
            evidence=output.get("evidence", []),
            knowledge_citations=output.get("knowledge_citations", []),
            report_previews=report_previews,
            report_count=report_count,
            training_previews=training_previews,
            training_count=training_count,
            tool_trace=output.get("tool_trace", []),
            pending_action=output.get("pending_action"),
            guided_selection=output.get("guided_selection"),
            degraded=output.get("degraded", False),
            error_code=output.get("error_code"),
        )
        return localize_response(response, locale)

    def answer(self, request: ChatRequest, *, locale: SupportedLocale = DEFAULT_LOCALE) -> ChatResponse:
        return self._run_chat_pipeline(request, locale=locale)

    async def answer_stream(
        self,
        request: ChatRequest,
        *,
        locale: SupportedLocale = DEFAULT_LOCALE,
    ) -> AsyncIterator[ChatStreamEvent]:
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[ChatStreamEvent | None] = asyncio.Queue()

        def emit_stage(stage: ChatStreamStage, tool_name: str | None, purpose: str | None) -> None:
            event = localize_response(
                ChatStreamEvent(stage=stage, tool_name=tool_name, purpose=purpose),
                locale,
            )
            loop.call_soon_threadsafe(queue.put_nowait, event)

        def run_sync() -> None:
            try:
                response = self._run_chat_pipeline(
                    request,
                    locale=locale,
                    stage_callback=emit_stage,
                )
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    ChatStreamEvent(stage="completed", response=response),
                )
            except Exception as exc:
                logger.exception("Streaming chat pipeline failed")
                loop.call_soon_threadsafe(
                    queue.put_nowait,
                    localize_response(
                        ChatStreamEvent(stage="error", detail=str(exc)[:256]),
                        locale,
                    ),
                )
            finally:
                loop.call_soon_threadsafe(queue.put_nowait, None)

        worker = asyncio.create_task(asyncio.to_thread(run_sync))
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield item
        finally:
            await asyncio.gather(worker, return_exceptions=True)


def _report_previews(results: list[ToolResult]) -> tuple[list[ReportPreview], int]:
    rows: dict[str, ReportPreview] = {}
    for result in results:
        if result.tool_name == "list_safety_reports" and isinstance(result.data, list):
            for item in result.data:
                if isinstance(item, dict):
                    preview = ReportPreview.model_validate(item)
                    rows[preview.report_id] = preview
        elif result.tool_name == "get_safety_report" and isinstance(result.data, dict):
            item = result.data
            preview = ReportPreview.model_validate({
                "report_id": item["report_id"], "period_start_utc": item["period_start_utc"],
                "period_end_utc": item["period_end_utc"], "status": item["status"],
                "event_count": item.get("statistics", {}).get("total", 0),
                "summary": item.get("content", {}).get("summary", ""), "pdf_url": item.get("pdf_url"),
            })
            rows[preview.report_id] = preview
    return list(rows.values())[:10], len(rows)


def _training_previews(results: list[ToolResult]) -> tuple[list[TrainingPreview], int]:
    rows: dict[str, TrainingPreview] = {}
    for result in results:
        if result.tool_name == "list_training_tasks" and isinstance(result.data, list):
            for item in result.data:
                if isinstance(item, dict):
                    preview = TrainingPreview.model_validate(item)
                    rows[preview.training_id] = preview
        elif result.tool_name == "get_training_task" and isinstance(result.data, dict):
            item = result.data
            preview = TrainingPreview.model_validate({
                "training_id": item["task_id"], "report_id": item["report_id"],
                "title": item["title"], "status": item["status"],
                "target_count": item["target_count"], "question_count": item["question_count"],
                "material_preview": item.get("material", "")[:300], "public_url": item.get("public_url"),
            })
            rows[preview.training_id] = preview
    return list(rows.values())[:10], len(rows)
