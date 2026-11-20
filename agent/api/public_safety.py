from __future__ import annotations

import asyncio
from datetime import datetime
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agent.api.dependencies import get_perception_service, get_request_locale
from agent.contracts.event_v1 import EventStatus, ViolationSeverity, ViolationType
from agent.contracts.query import CameraStatusResponse, RiskHeatmapResponse, SafetyQueryRequest, SafetyQueryResponse, ViolationPageResponse, ViolationQuery, ViolationStatisticsResponse
from agent.i18n import SupportedLocale, localize_response
from agent.services.perception_service import PerceptionService
from agent.services.sse_serializer import format_sse_comment, format_sse_event

router = APIRouter(prefix="/api/v1", tags=["safety"])


@router.get("/cameras", response_model=list[CameraStatusResponse])
def list_cameras(
    service: PerceptionService = Depends(get_perception_service),
    locale: SupportedLocale = Depends(get_request_locale),
) -> list[CameraStatusResponse]:
    return localize_response(service.list_camera_statuses(), locale)


@router.get("/violations", response_model=ViolationPageResponse)
def list_violations(
    camera_id: str | None = None, violation_type: ViolationType | None = None, severity: ViolationSeverity | None = None,
    status: EventStatus | None = None, start_time_utc: datetime | None = None, end_time_utc: datetime | None = None,
    limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0),
    service: PerceptionService = Depends(get_perception_service),
    locale: SupportedLocale = Depends(get_request_locale),
) -> ViolationPageResponse:
    return localize_response(
        service.query_violations_page(ViolationQuery(camera_id=camera_id, violation_type=violation_type, severity=severity, status=status, start_time_utc=start_time_utc, end_time_utc=end_time_utc, limit=limit, offset=offset)),
        locale,
    )


@router.get("/violations/statistics", response_model=ViolationStatisticsResponse)
def violation_statistics(camera_id: str | None = None, start_time_utc: datetime | None = None, end_time_utc: datetime | None = None, service: PerceptionService = Depends(get_perception_service)) -> ViolationStatisticsResponse:
    return service.get_statistics(ViolationQuery(camera_id=camera_id, start_time_utc=start_time_utc, end_time_utc=end_time_utc))


@router.get("/cameras/{camera_id}/status", response_model=CameraStatusResponse)
def camera_status(
    camera_id: str,
    service: PerceptionService = Depends(get_perception_service),
    locale: SupportedLocale = Depends(get_request_locale),
) -> CameraStatusResponse:
    result = service.get_camera_status(camera_id)
    if result is None:
        raise HTTPException(status_code=404, detail="camera status not found")
    return localize_response(result, locale)


@router.post("/agent/safety-query", response_model=SafetyQueryResponse)
def safety_query(
    request: SafetyQueryRequest,
    service: PerceptionService = Depends(get_perception_service),
    locale: SupportedLocale = Depends(get_request_locale),
) -> SafetyQueryResponse:
    return localize_response(service.run_safety_query(request), locale)


@router.get("/safety/risk-heatmap", response_model=RiskHeatmapResponse)
def risk_heatmap(
    lookback_days: int = Query(default=7, ge=1, le=30),
    timezone_offset_hours: int = Query(default=8, ge=-12, le=14),
    service: PerceptionService = Depends(get_perception_service),
    locale: SupportedLocale = Depends(get_request_locale),
) -> RiskHeatmapResponse:
    return localize_response(service.get_risk_heatmap(lookback_days, timezone_offset_hours), locale)


class FeishuTestRequest(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=128)
    content: str | None = Field(default=None, min_length=1, max_length=4000)


@router.post("/safety/notifications/feishu/test")
def test_feishu_notification(payload: FeishuTestRequest, request: Request) -> dict[str, Any]:
    notification_service = getattr(request.app.state, "notification_service", None)
    if notification_service is None or not notification_service.is_configured:
        raise HTTPException(status_code=503, detail="Feishu webhook notification is not configured")
    settings = getattr(request.app.state, "settings", None)
    title = (payload.title or "").strip() or getattr(settings, "feishu_test_default_title", "施工安全飞书联动自检通报")
    content = (payload.content or "").strip() or getattr(
        settings,
        "feishu_test_default_content",
        "✅ 飞书自定义机器人通知通道自检成功。",
    ).strip()
    result = notification_service.send_custom_briefing(title, content, sync=True)
    if not isinstance(result, dict) or not result.get("ok"):
        raise HTTPException(status_code=502, detail=f"Feishu webhook delivery failed: {result}")
    return {"status": "sent", "detail": result}


@router.get("/safety/events/stream")
async def stream_safety_events(
    request: Request,
    max_events: int = Query(default=0, ge=0, description="Max events to yield before closing stream (0 for infinite)"),
    locale: SupportedLocale = Depends(get_request_locale),
) -> StreamingResponse:
    broadcaster = getattr(request.app.state, "broadcaster", None)
    if broadcaster is None:
        raise HTTPException(status_code=503, detail="Realtime event broadcasting is not available")

    settings = getattr(request.app.state, "settings", None)
    keepalive_seconds = float(getattr(settings, "sse_keepalive_seconds", 15.0))

    async def event_generator():
        yield format_sse_event("ping", {"connected": True})
        yielded_count = 1
        if max_events > 0 and yielded_count >= max_events:
            return

        iterator = broadcaster.subscribe()
        last_keepalive = time.monotonic()
        try:
            while not await request.is_disconnected():
                item = await asyncio.to_thread(lambda: next(iterator, None))
                if item is None:
                    now = time.monotonic()
                    if (now - last_keepalive) >= keepalive_seconds:
                        yield format_sse_comment()
                        last_keepalive = now
                    continue
                event_type = item.get("event_type", "message")
                data = localize_response(item.get("data", {}), locale)
                yield format_sse_event(event_type, data)
                last_keepalive = time.monotonic()
                yielded_count += 1
                if max_events > 0 and yielded_count >= max_events:
                    break
        except (asyncio.CancelledError, GeneratorExit):
            pass
        finally:
            if hasattr(iterator, "close"):
                try:
                    iterator.close()
                except Exception:
                    pass

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
