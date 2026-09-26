from __future__ import annotations

from uuid import uuid4

from agent.contracts.chat import ChatRequest, ChatResponse
from agent.db.base import Database
from agent.graph.chat_graph import build_chat_graph
from agent.llm.protocol import ChatModelPort
from agent.repositories.violations import ViolationRepository
from agent.services.conversation_memory import ConversationMemory
from agent.services.knowledge_service import KnowledgeService


class ChatService:
    def __init__(self, database: Database, model: ChatModelPort, max_tool_calls: int = 2, memory_enabled: bool = True, memory_ttl_hours: int = 24, memory_recent_turns: int = 6, knowledge_service: KnowledgeService | None = None):
        self.database = database
        self.model = model
        self.max_tool_calls = max_tool_calls
        self.memory_enabled, self.memory_ttl_hours, self.memory_recent_turns = memory_enabled, memory_ttl_hours, memory_recent_turns
        self.knowledge_service = knowledge_service

    def answer(self, request: ChatRequest) -> ChatResponse:
        request_id = str(uuid4())
        with self.database.session() as session:
            memory = ConversationMemory(session, self.memory_ttl_hours, self.memory_recent_turns)
            if self.memory_enabled:
                memory.cleanup_expired()
            context = memory.load_context(request.conversation_id) if self.memory_enabled else ""
            graph = build_chat_graph(ViolationRepository(session), self.model, self.max_tool_calls, self.knowledge_service)
            output = graph.invoke({
                "request_id": request_id,
                "question": request.question,
                "conversation_id": request.conversation_id,
                "tool_results": [],
                "tool_trace": [],
                "evidence": [],
                "knowledge_citations": [],
                "memory_context": context,
                "degraded": False,
            })
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
            degraded=output.get("degraded", False),
            error_code=output.get("error_code"),
        )
