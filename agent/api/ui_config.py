from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, HTTPException, Request

from agent.contracts.ui_config import AssistantUiConfig, AssistantUiConfigUpdate
from agent.services.ui_config_service import UiConfigService

public_router = APIRouter(prefix="/api/v1/agent", tags=["agent-ui"])
admin_router = APIRouter(prefix="/api/v1/admin/agent", tags=["agent-ui-admin"])


@public_router.get("/ui-config", response_model=AssistantUiConfig)
def get_ui_config(request: Request) -> AssistantUiConfig:
    with request.app.state.database.session() as session:
        config = UiConfigService(session).get()
        if not config:
            return AssistantUiConfig(version=0, assistant_name="安全智能助手",
                welcome_message="查询现场风险，核对安全依据，衔接报告与培训。",
                input_placeholder="例如：查看本周安全报告，或查询长沙当前天气",
                quick_questions=["查看所有摄像头状态", "查看最新违规事件", "查看本周安全报告"],
                show_evidence=True, updated_at_utc=datetime(1970, 1, 1, tzinfo=timezone.utc))
        return config


@admin_router.put("/ui-config", response_model=AssistantUiConfig)
def put_ui_config(value: AssistantUiConfigUpdate, request: Request) -> AssistantUiConfig:
    try:
        with request.app.state.database.session() as session:
            return UiConfigService(session).put(value, "local")
    except RuntimeError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
