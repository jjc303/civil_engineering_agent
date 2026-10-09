from __future__ import annotations

from uuid import uuid4
import logging

from agent.contracts.chat import ChatRequest, ChatResponse
from agent.db.base import Database
from agent.graph.chat_graph import build_chat_graph
from agent.llm.protocol import ChatModelPort
from agent.repositories.violations import ViolationRepository
from agent.services.conversation_memory import ConversationMemory
from agent.services.knowledge_service import KnowledgeService
from agent.services.agent_write_actions import AgentWriteActionService

logger = logging.getLogger(__name__)


class ChatService:
    def __init__(self, database: Database, model: ChatModelPort, max_tool_calls: int = 2, memory_enabled: bool = True, memory_ttl_hours: int = 24, memory_recent_turns: int = 6, knowledge_service: KnowledgeService | None = None, write_action_service: AgentWriteActionService | None = None, standards_top_k: int = 4):
        self.database = database
        self.model = model
        self.max_tool_calls = max_tool_calls
        self.memory_enabled, self.memory_ttl_hours, self.memory_recent_turns = memory_enabled, memory_ttl_hours, memory_recent_turns
        self.knowledge_service = knowledge_service
        self.write_action_service = write_action_service
        self.standards_top_k = standards_top_k

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
            graph = build_chat_graph(ViolationRepository(session), self.model, self.max_tool_calls, self.knowledge_service, self.write_action_service)
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
        return ChatResponse(
            request_id=request_id,
            answer=output.get("answer", "安全问答服务暂时不可用，请稍后重试。"),
            evidence=output.get("evidence", []),
            knowledge_citations=output.get("knowledge_citations", []),
            tool_trace=output.get("tool_trace", []),
            pending_action=output.get("pending_action"),
            guided_selection=output.get("guided_selection"),
            degraded=output.get("degraded", False),
            error_code=output.get("error_code"),
        )
