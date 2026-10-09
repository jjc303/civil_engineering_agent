from __future__ import annotations

from uuid import uuid4
import logging

from agent.contracts.chat import ChatRequest, ChatResponse, ReportPreview, ToolResult, TrainingPreview
from agent.db.base import Database
from agent.graph.chat_graph import build_chat_graph
from agent.llm.protocol import ChatModelPort
from agent.repositories.violations import ViolationRepository
from agent.services.conversation_memory import ConversationMemory
from agent.services.knowledge_service import KnowledgeService
from agent.services.agent_write_actions import AgentWriteActionService
from agent.services.learning_service import LearningService

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(self, database: Database, model: ChatModelPort, max_tool_calls: int = 2, memory_enabled: bool = True, memory_ttl_hours: int = 24, memory_recent_turns: int = 6, knowledge_service: KnowledgeService | None = None, write_action_service: AgentWriteActionService | None = None, standards_top_k: int = 4, learning_service: LearningService | None = None):
        self.database = database
        self.model = model
        self.max_tool_calls = max_tool_calls
        self.memory_enabled, self.memory_ttl_hours, self.memory_recent_turns = memory_enabled, memory_ttl_hours, memory_recent_turns
        self.knowledge_service = knowledge_service
        self.write_action_service = write_action_service
        self.standards_top_k = standards_top_k
        self.learning_service = learning_service

    def answer(self, request: ChatRequest) -> ChatResponse:
        request_id = str(uuid4())
        with self.database.session() as session:
            memory = ConversationMemory(session, self.memory_ttl_hours, self.memory_recent_turns)
            if self.memory_enabled:
                memory.cleanup_expired()
            context = memory.load_context(request.conversation_id) if self.memory_enabled else ""
            standards_context = "当前有效规范库未检索到相关片段。不得自行补充标准名称、编号或条款。"
            standard_citations = []
            standards_error = None
            if self.knowledge_service:
                try:
                    fragments, standard_citations = self.knowledge_service.search_standards(request.question, self.standards_top_k)
                    if fragments:
                        standards_context = "\n\n".join(
                            f"来源：{item['title']}；章节：{item['page_or_section']}；出处：{item['source_label']}；有效性：{item['validity_status']}\n{item['content']}"
                            for item in fragments
                        )
                except Exception:
                    logger.exception("Automatic standards retrieval failed")
                    standards_context = "规范库检索暂时不可用。不得自行补充标准名称、编号或条款。"
                    standards_error = "STANDARDS_RETRIEVAL_FAILED"
            graph = build_chat_graph(ViolationRepository(session), self.model, self.max_tool_calls, self.knowledge_service, self.write_action_service, self.learning_service)
            output = graph.invoke({
                "request_id": request_id,
                "question": request.question,
                "conversation_id": request.conversation_id,
                "tool_results": [],
                "tool_trace": [],
                "evidence": [],
                "knowledge_citations": standard_citations,
                "memory_context": context,
                "standards_context": standards_context,
                "degraded": False,
            })
            if standards_error:
                output["degraded"] = True
                output["error_code"] = output.get("error_code") or standards_error
            if self.memory_enabled:
                try:
                    memory.persist(request.conversation_id, request.question, output.get("answer", ""), output.get("tool_results", []), output.get("tool_trace", []), output.get("knowledge_citations", []))
                except Exception:
                    output["degraded"] = True
                    output["error_code"] = output.get("error_code") or "MEMORY_PERSIST_FAILED"
        report_previews, report_count = _report_previews(output.get("tool_results", []))
        training_previews, training_count = _training_previews(output.get("tool_results", []))
        return ChatResponse(
            request_id=request_id,
            answer=output.get("answer", "安全问答服务暂时不可用，请稍后重试。"),
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
