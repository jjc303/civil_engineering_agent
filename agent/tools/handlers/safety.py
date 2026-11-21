from __future__ import annotations

from agent.contracts.chat import ToolDecision
from agent.contracts.query import ViolationQuery
from agent.domain.time_context import (
    enrich_record_local_times,
    enrich_records_local_times,
    resolve_context_timezone,
)
from agent.tools import safety_tools
from agent.tools.base import AgentTool, ToolContext, ToolOutcome, extract_evidence

_VIOLATION_TIME_FIELDS = (
    ("occurred_at_utc", "occurred_at_local"),
    ("resolved_at_utc", "resolved_at_local"),
)
_CAMERA_TIME_FIELDS = (("reported_at_utc", "reported_at_local"),)


def _query_violations(decision: ToolDecision, ctx: ToolContext) -> ToolOutcome:
    query = ViolationQuery.model_validate(decision.query.model_dump(mode="json"))
    raw_rows = [item.model_dump(mode="json") for item in ctx.repository.query_events(query)]
    tz = resolve_context_timezone(ctx)
    data = enrich_records_local_times(raw_rows, _VIOLATION_TIME_FIELDS, tz)
    return ToolOutcome(data=data, evidence=extract_evidence(raw_rows))


def _get_violation_statistics(decision: ToolDecision, ctx: ToolContext) -> ToolOutcome:
    query = ViolationQuery.model_validate(decision.query.model_dump(mode="json"))
    data = ctx.repository.get_statistics(query).model_dump(mode="json")
    return ToolOutcome(data=data)


def _get_camera_status(decision: ToolDecision, ctx: ToolContext) -> ToolOutcome:
    status = ctx.repository.get_camera_status(decision.camera_id) if decision.camera_id else None
    if status is None:
        return ToolOutcome(data=None)
    tz = resolve_context_timezone(ctx)
    data = enrich_record_local_times(status.model_dump(mode="json"), _CAMERA_TIME_FIELDS, tz)
    return ToolOutcome(data=data)


def _get_all_camera_statuses(_decision: ToolDecision, ctx: ToolContext) -> ToolOutcome:
    raw_rows = [status.model_dump(mode="json") for status in ctx.repository.list_camera_statuses()]
    tz = resolve_context_timezone(ctx)
    data = enrich_records_local_times(raw_rows, _CAMERA_TIME_FIELDS, tz)
    return ToolOutcome(data=data)


def _get_workforce_summary(_decision: ToolDecision, ctx: ToolContext) -> ToolOutcome:
    return ToolOutcome(data=ctx.repository.get_workforce_summary())


def _get_current_weather(decision: ToolDecision, _ctx: ToolContext) -> ToolOutcome:
    data = safety_tools.get_current_weather(decision.weather_location or "").model_dump(mode="json")
    return ToolOutcome(data=data)


SAFETY_TOOLS: tuple[AgentTool, ...] = (
    AgentTool(
        name="query_violations",
        description="查询已入库的违规事件明细。",
        parameters="query: ViolationQuery",
        handler=_query_violations,
        intent_keywords=("违规", "事件", "记录", "隐患", "安全帽", "危险区", "违章"),
    ),
    AgentTool(
        name="get_violation_statistics",
        description="汇总已入库的违规数量、类型和严重级别。",
        parameters="query: ViolationQuery",
        handler=_get_violation_statistics,
        intent_keywords=("违规", "事件", "统计", "汇总", "多少", "几条"),
    ),
    AgentTool(
        name="get_camera_status",
        description="查询一个明确 camera_id 的最新状态。",
        parameters="camera_id: string",
        handler=_get_camera_status,
        intent_keywords=("摄像头", "监控", "相机", "状态", "在线", "离线", "fps", "帧率", "画面"),
    ),
    AgentTool(
        name="get_all_camera_statuses",
        description="列出所有已知摄像头的最新状态。",
        parameters="none",
        handler=_get_all_camera_statuses,
        intent_keywords=("摄像头", "监控", "相机", "巡检", "人数", "工人", "状态", "在线", "离线", "画面"),
    ),
    AgentTool(
        name="get_workforce_summary",
        description="汇总在线摄像头上报的活跃作业人数，不进行跨摄像头人员去重。",
        parameters="none",
        handler=_get_workforce_summary,
        intent_keywords=("人数", "工人", "人员", "在场", "作业"),
    ),
    AgentTool(
        name="get_current_weather",
        description="查询一个明确地点的当前天气。",
        parameters="location: string",
        handler=_get_current_weather,
        intent_keywords=("天气", "气温", "温度", "下雨", "降雨", "风力", "风速", "气象"),
    ),
)
