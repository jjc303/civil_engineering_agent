from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from agent.api.dependencies import get_request_locale
from agent.contracts.ui_config import AssistantUiConfig, AssistantUiConfigUpdate
from agent.i18n import SupportedLocale, localize_response
from agent.services.ui_config_service import UiConfigService

public_router = APIRouter(prefix="/api/v1/agent", tags=["agent-ui"])
admin_router = APIRouter(prefix="/api/v1/admin/agent", tags=["agent-ui-admin"])


@public_router.get("/ui-config", response_model=AssistantUiConfig)
def get_ui_config(
    request: Request,
    locale: SupportedLocale = Depends(get_request_locale),
) -> AssistantUiConfig:
    with request.app.state.database.session() as session:
        return localize_response(UiConfigService(session).get_or_default(), locale)


@admin_router.put("/ui-config", response_model=AssistantUiConfig)
def put_ui_config(value: AssistantUiConfigUpdate, request: Request) -> AssistantUiConfig:
    try:
        with request.app.state.database.session() as session:
            return UiConfigService(session).put(value, "local")
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
