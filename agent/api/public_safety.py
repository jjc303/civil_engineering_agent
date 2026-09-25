from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query

from agent.api.dependencies import get_perception_service
from agent.contracts.event_v1 import EventStatus, ViolationSeverity, ViolationType
from agent.contracts.query import CameraStatusResponse, SafetyQueryRequest, SafetyQueryResponse, ViolationQuery, ViolationRecord, ViolationStatisticsResponse
from agent.services.perception_service import PerceptionService

router = APIRouter(prefix="/api/v1", tags=["safety"])


@router.get("/violations", response_model=list[ViolationRecord])
def list_violations(
    camera_id: str | None = None, violation_type: ViolationType | None = None, severity: ViolationSeverity | None = None,
    status: EventStatus | None = None, start_time_utc: datetime | None = None, end_time_utc: datetime | None = None,
    limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0),
    service: PerceptionService = Depends(get_perception_service),
) -> list[ViolationRecord]:
    return service.query_violations(ViolationQuery(camera_id=camera_id, violation_type=violation_type, severity=severity, status=status, start_time_utc=start_time_utc, end_time_utc=end_time_utc, limit=limit, offset=offset))


@router.get("/violations/statistics", response_model=ViolationStatisticsResponse)
def violation_statistics(camera_id: str | None = None, start_time_utc: datetime | None = None, end_time_utc: datetime | None = None, service: PerceptionService = Depends(get_perception_service)) -> ViolationStatisticsResponse:
    return service.get_statistics(ViolationQuery(camera_id=camera_id, start_time_utc=start_time_utc, end_time_utc=end_time_utc))


@router.get("/cameras/{camera_id}/status", response_model=CameraStatusResponse)
def camera_status(camera_id: str, service: PerceptionService = Depends(get_perception_service)) -> CameraStatusResponse:
    result = service.get_camera_status(camera_id)
    if result is None:
        raise HTTPException(status_code=404, detail="camera status not found")
    return result


@router.post("/agent/safety-query", response_model=SafetyQueryResponse)
def safety_query(request: SafetyQueryRequest, service: PerceptionService = Depends(get_perception_service)) -> SafetyQueryResponse:
    return service.run_safety_query(request)
