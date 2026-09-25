from __future__ import annotations

from uuid import uuid4

from agent.contracts.chat import ChatRequest, ChatResponse
from agent.db.base import Database
from agent.graph.chat_graph import build_chat_graph
from agent.llm.protocol import ChatModelPort
from agent.repositories.violations import ViolationRepository


class ChatService:
    def __init__(self, database: Database, model: ChatModelPort, max_tool_calls: int = 2):
        self.database = database
        self.model = model
        self.max_tool_calls = max_tool_calls

    def answer(self, request: ChatRequest) -> ChatResponse:
        request_id = str(uuid4())
        with self.database.session() as session:
            graph = build_chat_graph(ViolationRepository(session), self.model, self.max_tool_calls)
            output = graph.invoke({
                "request_id": request_id,
                "question": request.question,
                "conversation_id": request.conversation_id,
                "tool_results": [],
                "tool_trace": [],
                "evidence": [],
                "degraded": False,
            })
        return ChatResponse(
            request_id=request_id,
            answer=output.get("answer", "安全问答服务暂时不可用，请稍后重试。"),
            evidence=output.get("evidence", []),
            tool_trace=output.get("tool_trace", []),
            degraded=output.get("degraded", False),
            error_code=output.get("error_code"),
        )
