from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials

from agent.api.dependencies import get_perception_service
from agent.contracts.event_v1 import CameraStatusReportV1, EventUpsertResponse, SafetyViolationEventV1
from agent.core.security import bearer_scheme, verify_internal_token
from agent.services.perception_service import PerceptionService

router = APIRouter(prefix="/internal/v1/perception", tags=["internal-perception"])


def require_internal_token(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> None:
    verify_internal_token(credentials, request.app.state.settings)


@router.get("/health", dependencies=[Depends(require_internal_token)])
def perception_health() -> dict[str, str]:
    return {"status": "ok"}


@router.post("/events", response_model=EventUpsertResponse, dependencies=[Depends(require_internal_token)])
def upsert_event(event: SafetyViolationEventV1, service: PerceptionService = Depends(get_perception_service)) -> EventUpsertResponse:
    return service.upsert_event(event)


@router.put("/cameras/{camera_id}/status", dependencies=[Depends(require_internal_token)])
def upsert_camera_status(camera_id: str, report: CameraStatusReportV1, service: PerceptionService = Depends(get_perception_service)):
    if camera_id != report.camera_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=422, detail="camera_id path/body mismatch")
    return service.upsert_camera_status(report)
