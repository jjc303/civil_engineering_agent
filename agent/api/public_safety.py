from __future__ import annotations

import asyncio
from datetime import datetime
import json
import time
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from agent.api.dependencies import get_perception_service
from agent.contracts.event_v1 import EventStatus, ViolationSeverity, ViolationType
from agent.contracts.query import CameraStatusResponse, RiskHeatmapResponse, SafetyQueryRequest, SafetyQueryResponse, ViolationPageResponse, ViolationQuery, ViolationStatisticsResponse
from agent.services.perception_service import PerceptionService

router = APIRouter(prefix="/api/v1", tags=["safety"])


@router.get("/cameras", response_model=list[CameraStatusResponse])
def list_cameras(service: PerceptionService = Depends(get_perception_service)) -> list[CameraStatusResponse]:
    return service.list_camera_statuses()


@router.get("/violations", response_model=ViolationPageResponse)
def list_violations(
    camera_id: str | None = None, violation_type: ViolationType | None = None, severity: ViolationSeverity | None = None,
    status: EventStatus | None = None, start_time_utc: datetime | None = None, end_time_utc: datetime | None = None,
    limit: int = Query(default=100, ge=1, le=500), offset: int = Query(default=0, ge=0),
    service: PerceptionService = Depends(get_perception_service),
) -> ViolationPageResponse:
    return service.query_violations_page(ViolationQuery(camera_id=camera_id, violation_type=violation_type, severity=severity, status=status, start_time_utc=start_time_utc, end_time_utc=end_time_utc, limit=limit, offset=offset))


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


@router.get("/safety/risk-heatmap", response_model=RiskHeatmapResponse)
def risk_heatmap(
    lookback_days: int = Query(default=7, ge=1, le=30),
    timezone_offset_hours: int = Query(default=8, ge=-12, le=14),
    service: PerceptionService = Depends(get_perception_service),
) -> RiskHeatmapResponse:
    return service.get_risk_heatmap(lookback_days, timezone_offset_hours)


class FeishuTestRequest(BaseModel):
    title: str = Field(default="国赛演练 · 现场安全态势实时联动测试", min_length=1, max_length=128)
    content: str = Field(
        default="✅ **飞书自定义机器人通道已就绪**\n- 边缘感知高危违规秒级告警已开启\n- 整改任务派发与销项闭环通知已开启\n- 安全周报与全员培训发布推送已开启",
        min_length=1,
        max_length=4000,
    )


@router.post("/safety/notifications/feishu/test")
def test_feishu_notification(payload: FeishuTestRequest, request: Request) -> dict[str, Any]:
    notification_service = getattr(request.app.state, "notification_service", None)
    if notification_service is None or not notification_service.is_configured:
        raise HTTPException(status_code=503, detail="Feishu webhook notification is not configured")
    result = notification_service.send_custom_briefing(payload.title, payload.content, sync=True)
    if not result or not result.get("ok"):
        raise HTTPException(status_code=502, detail=f"Feishu webhook delivery failed: {result}")
    return {"status": "sent", "detail": result}


@router.get("/safety/events/stream")
async def stream_safety_events(
    request: Request,
    max_events: int = Query(default=0, ge=0, description="Max events to yield before closing stream (0 for infinite)"),
) -> StreamingResponse:
    broadcaster = getattr(request.app.state, "broadcaster", None)
    if broadcaster is None:
        raise HTTPException(status_code=503, detail="Realtime event broadcasting is not available")

    async def event_generator():
        yield f"event: ping\ndata: {{\"connected\": true}}\n\n"
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
                    if (now - last_keepalive) >= 15.0:
                        yield ": keepalive\n\n"
                        last_keepalive = now
                    continue
                event_type = item.get("event_type", "message")
                payload = json.dumps(item.get("data", {}), ensure_ascii=False)
                yield f"event: {event_type}\ndata: {payload}\n\n"
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
