from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agent.api.dependencies import get_chat_service, get_request_locale, get_write_action_service
from agent.contracts.actions import ActionConfirmationRequest, ActionExecutionResponse, PendingActionResponse
from agent.contracts.chat import ChatRequest, ChatResponse, ToolDecision
from agent.contracts.learning import TrainingCreate
from agent.i18n import SupportedLocale, localize_response
from agent.services.agent_write_actions import AgentWriteActionError
from agent.services.sse_serializer import format_sse_event

router = APIRouter(prefix="/api/v1/agent", tags=["agent-chat"])


@router.post("/chat", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    http_request: Request,
    locale: SupportedLocale = Depends(get_request_locale),
) -> ChatResponse:
    return get_chat_service(http_request).answer(request, locale=locale)


@router.post("/chat/stream")
async def chat_stream(
    request: ChatRequest,
    http_request: Request,
    locale: SupportedLocale = Depends(get_request_locale),
) -> StreamingResponse:
    chat_service = get_chat_service(http_request)

    async def event_generator():
        async for event in chat_service.answer_stream(request, locale=locale):
            yield format_sse_event(event.stage, event)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


class TrainingActionProposal(BaseModel):
    conversation_id: str = Field(min_length=1, max_length=128)
    training: TrainingCreate


@router.post("/learning/training/propose", response_model=PendingActionResponse)
def propose_training(
    request: TrainingActionProposal,
    http_request: Request,
    locale: SupportedLocale = Depends(get_request_locale),
) -> PendingActionResponse:
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
        return localize_response(
            get_write_action_service(http_request).propose(request.conversation_id, decision),
            locale,
        )
    except AgentWriteActionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/actions/{confirmation_id}/confirm", response_model=ActionExecutionResponse)
def confirm_action(
    confirmation_id: str,
    request: ActionConfirmationRequest,
    http_request: Request,
    locale: SupportedLocale = Depends(get_request_locale),
) -> ActionExecutionResponse:
    try:
        return localize_response(
            get_write_action_service(http_request).confirm(confirmation_id, request.conversation_id),
            locale,
        )
    except AgentWriteActionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/actions/{confirmation_id}/cancel", response_model=ActionExecutionResponse)
def cancel_action(
    confirmation_id: str,
    request: ActionConfirmationRequest,
    http_request: Request,
    locale: SupportedLocale = Depends(get_request_locale),
) -> ActionExecutionResponse:
    try:
        return localize_response(
            get_write_action_service(http_request).cancel(confirmation_id, request.conversation_id),
            locale,
        )
    except AgentWriteActionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
