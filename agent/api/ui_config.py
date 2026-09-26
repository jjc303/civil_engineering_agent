from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from agent.api.camera_management import require_admin
from agent.contracts.ui_config import AssistantUiConfig, AssistantUiConfigUpdate
from agent.services.ui_config_service import UiConfigService

public_router = APIRouter(prefix="/api/v1/agent", tags=["agent-ui"])
admin_router = APIRouter(prefix="/api/v1/admin/agent", tags=["agent-ui-admin"], dependencies=[Depends(require_admin)])


@public_router.get("/ui-config", response_model=AssistantUiConfig)
def get_ui_config(request: Request) -> AssistantUiConfig:
    with request.app.state.database.session() as session:
        config = UiConfigService(session).get()
        if not config: raise HTTPException(status_code=404, detail="assistant UI configuration has not been published")
        return config


@admin_router.put("/ui-config", response_model=AssistantUiConfig)
def put_ui_config(value: AssistantUiConfigUpdate, request: Request) -> AssistantUiConfig:
    try:
        with request.app.state.database.session() as session:
            return UiConfigService(session).put(value, "admin")
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
