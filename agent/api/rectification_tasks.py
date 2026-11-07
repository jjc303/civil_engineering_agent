from __future__ import annotations

from fastapi import APIRouter, HTTPException, Query, Request

from agent.api.dependencies import get_rectification_task_service as _service
from agent.contracts.rectification import (
    RectificationPendingActionResponse,
    RectificationTaskCreateRequest,
    RectificationTaskDetail,
    RectificationTaskPageResponse,
    RectificationTaskRecord,
    RectificationTaskUpdateRequest,
)
from agent.services.agent_write_actions import AgentWriteActionError

router = APIRouter(prefix="/api/v1/rectification-tasks", tags=["rectification-tasks"])


@router.get("", response_model=RectificationTaskPageResponse)
def list_tasks(
    request: Request, status: str | None = None, owner: str | None = None, overdue: bool | None = None,
    limit: int = Query(default=20, ge=1, le=100), offset: int = Query(default=0, ge=0),
) -> RectificationTaskPageResponse:
    return _service(request).list_tasks(status=status, owner=owner, overdue=overdue, limit=limit, offset=offset)


@router.post("", response_model=RectificationTaskRecord)
def create_task(payload: RectificationTaskCreateRequest, request: Request) -> RectificationTaskRecord:
    try:
        return _service(request).create_task(payload)
    except AgentWriteActionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.get("/{task_id}", response_model=RectificationTaskDetail)
def get_task(task_id: str, request: Request) -> RectificationTaskDetail:
    try:
        return _service(request).get_task(task_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="rectification task not found") from exc


@router.patch("/{task_id}", response_model=RectificationTaskRecord)
def update_task(task_id: str, payload: RectificationTaskUpdateRequest, request: Request) -> RectificationTaskRecord:
    try:
        return _service(request).update_task(task_id, payload)
    except AgentWriteActionError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="rectification task not found") from exc
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


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
