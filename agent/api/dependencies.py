from __future__ import annotations

from fastapi import Request

from agent.services.perception_service import PerceptionService
from agent.services.camera_management import CameraManagementService


def get_perception_service(request: Request) -> PerceptionService:
    return request.app.state.perception_service


def get_camera_management_service(request: Request) -> CameraManagementService:
    return request.app.state.camera_management_service
