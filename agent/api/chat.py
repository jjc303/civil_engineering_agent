from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request

from agent.contracts.actions import ActionConfirmationRequest, ActionExecutionResponse
from agent.contracts.chat import ChatRequest, ChatResponse
from agent.services.chat_service import ChatService
from agent.services.agent_write_actions import AgentWriteActionError, AgentWriteActionService

router = APIRouter(prefix="/api/v1/agent", tags=["agent-chat"])


def get_chat_service(request: Request) -> ChatService:
    return request.app.state.chat_service


def get_write_action_service(request: Request) -> AgentWriteActionService:
    return request.app.state.agent_write_action_service


@router.post("/chat", response_model=ChatResponse)
def chat(request: ChatRequest, http_request: Request) -> ChatResponse:
    return get_chat_service(http_request).answer(request)


@router.post("/actions/{confirmation_id}/confirm", response_model=ActionExecutionResponse)
def confirm_action(confirmation_id: str, request: ActionConfirmationRequest, http_request: Request) -> ActionExecutionResponse:
    try:
        return get_write_action_service(http_request).confirm(confirmation_id, request.conversation_id)
    except AgentWriteActionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/actions/{confirmation_id}/cancel", response_model=ActionExecutionResponse)
def cancel_action(confirmation_id: str, request: ActionConfirmationRequest, http_request: Request) -> ActionExecutionResponse:
    try:
        return get_write_action_service(http_request).cancel(confirmation_id, request.conversation_id)
    except AgentWriteActionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
