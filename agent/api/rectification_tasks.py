from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from agent.contracts.rectification import (
    RectificationPendingActionResponse,
    RectificationTaskCreateRequest,
    RectificationTaskDetail,
    RectificationTaskPageResponse,
    RectificationTaskUpdateRequest,
)
from agent.services.agent_write_actions import AgentWriteActionError
from agent.services.rectification_task_service import RectificationTaskService

router = APIRouter(prefix="/api/v1/rectification-tasks", tags=["rectification-tasks"])


def _service(request: Request) -> RectificationTaskService:
    return request.app.state.rectification_task_service


@router.get("", response_model=RectificationTaskPageResponse)
def list_tasks(
    request: Request, status: str | None = None, owner: str | None = None, overdue: bool | None = None,
    limit: int = Query(default=20, ge=1, le=100), offset: int = Query(default=0, ge=0),
) -> RectificationTaskPageResponse:
    return _service(request).list_tasks(status=status, owner=owner, overdue=overdue, limit=limit, offset=offset)


@router.get("/{task_id}", response_model=RectificationTaskDetail)
def get_task(task_id: str, request: Request) -> RectificationTaskDetail:
    try:
        return _service(request).get_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="rectification task not found") from exc


@router.post("/pending-create", response_model=RectificationPendingActionResponse)
def pending_create(payload: RectificationTaskCreateRequest, request: Request) -> RectificationPendingActionResponse:
    try:
        return RectificationPendingActionResponse(pending_action=_service(request).propose_create(payload))
    except AgentWriteActionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{task_id}/pending-update", response_model=RectificationPendingActionResponse)
def pending_update(task_id: str, payload: RectificationTaskUpdateRequest, request: Request) -> RectificationPendingActionResponse:
    try:
        return RectificationPendingActionResponse(pending_action=_service(request).propose_update(task_id, payload))
    except AgentWriteActionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
