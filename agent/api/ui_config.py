from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request

from agent.api.dependencies import get_request_locale
from agent.contracts.ui_config import AssistantUiConfig, AssistantUiConfigUpdate
from agent.i18n import SupportedLocale, localize_response
from agent.services.ui_config_service import UiConfigService, mascot_profile_from_settings

public_router = APIRouter(prefix="/api/v1/agent", tags=["agent-ui"])
admin_router = APIRouter(prefix="/api/v1/admin/agent", tags=["agent-ui-admin"])


def _resolve_admin_actor(request: Request) -> str:
    raw = (request.headers.get("x-admin-actor") or "").strip()
    return raw[:128] if raw else "local"


@public_router.get("/ui-config", response_model=AssistantUiConfig)
def get_ui_config(
    request: Request,
    locale: SupportedLocale = Depends(get_request_locale),
) -> AssistantUiConfig:
    settings = getattr(request.app.state, "settings", None)
    profile = mascot_profile_from_settings(settings)
    with request.app.state.database.session() as session:
        return localize_response(UiConfigService(session, mascot_profile=profile).get_or_default(), locale)


@admin_router.put("/ui-config", response_model=AssistantUiConfig)
def put_ui_config(value: AssistantUiConfigUpdate, request: Request) -> AssistantUiConfig:
    settings = getattr(request.app.state, "settings", None)
    profile = mascot_profile_from_settings(settings)
    actor = _resolve_admin_actor(request)
    try:
        with request.app.state.database.session() as session:
            return UiConfigService(session, mascot_profile=profile).put(value, actor)
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
