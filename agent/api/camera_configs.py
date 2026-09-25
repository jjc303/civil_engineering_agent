from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException

from agent.api.dependencies import get_perception_service
from agent.contracts.camera_config import CameraConfigUpdateRequest, CameraRunConfigV1
from agent.repositories.camera_configs import ConfigVersionConflict
from agent.services.perception_service import PerceptionService

router = APIRouter(prefix="/api/v1", tags=["camera-configurations"])


@router.put("/cameras/{camera_id}/zones", response_model=CameraRunConfigV1)
def update_camera_zones(
    camera_id: str,
    request: CameraConfigUpdateRequest,
    service: PerceptionService = Depends(get_perception_service),
) -> CameraRunConfigV1:
    try:
        return service.update_camera_config(camera_id, request)
    except ConfigVersionConflict as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
