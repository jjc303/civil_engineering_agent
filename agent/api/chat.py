from __future__ import annotations

from fastapi import APIRouter, Request

from agent.contracts.chat import ChatRequest, ChatResponse
from agent.services.chat_service import ChatService

router = APIRouter(prefix="/api/v1/agent", tags=["agent-chat"])


def get_chat_service(request: Request) -> ChatService:
    return request.app.state.chat_service


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, http_request: Request) -> ChatResponse:
    return get_chat_service(http_request).answer(request)
