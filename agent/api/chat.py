from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from agent.contracts.actions import ActionConfirmationRequest, ActionExecutionResponse, PendingActionResponse
from agent.contracts.chat import ChatRequest, ChatResponse, ToolDecision
from agent.contracts.learning import TrainingCreate
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


class TrainingActionProposal(BaseModel):
    conversation_id: str = Field(min_length=1, max_length=128)
    training: TrainingCreate


@router.post("/learning/training/propose", response_model=PendingActionResponse)
def propose_training(request: TrainingActionProposal, http_request: Request) -> PendingActionResponse:
    training = request.training
    decision = ToolDecision(
        tool_name="create_training_task",
        purpose="根据选定的已确认报告生成培训草稿",
        report_id=training.report_id,
        training_title=training.title,
        training_document_ids=training.document_ids,
        training_target_count=training.target_count,
        training_question_count=training.question_count,
        training_pass_score=training.pass_score,
    )
    try:
        return get_write_action_service(http_request).propose(request.conversation_id, decision)
    except AgentWriteActionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


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
