from __future__ import annotations

from fastapi import Request

from agent.services.perception_service import PerceptionService


def get_perception_service(request: Request) -> PerceptionService:
    return request.app.state.perception_service
