from __future__ import annotations

from agent.contracts.chat import ToolDecision
from agent.contracts.query import ViolationQuery
from agent.tools import safety_tools
from agent.tools.base import AgentTool, ToolContext, ToolOutcome, extract_evidence


def _query_violations(decision: ToolDecision, ctx: ToolContext) -> ToolOutcome:
    query = ViolationQuery.model_validate(decision.query.model_dump(mode="json"))
    data = [item.model_dump(mode="json") for item in ctx.repository.query_events(query)]
    return ToolOutcome(data=data, evidence=extract_evidence(data))


def _get_violation_statistics(decision: ToolDecision, ctx: ToolContext) -> ToolOutcome:
    query = ViolationQuery.model_validate(decision.query.model_dump(mode="json"))
    data = ctx.repository.get_statistics(query).model_dump(mode="json")
    return ToolOutcome(data=data)


def _get_camera_status(decision: ToolDecision, ctx: ToolContext) -> ToolOutcome:
    status = ctx.repository.get_camera_status(decision.camera_id) if decision.camera_id else None
    data = status.model_dump(mode="json") if status else None
    return ToolOutcome(data=data)


def _get_all_camera_statuses(_decision: ToolDecision, ctx: ToolContext) -> ToolOutcome:
    data = [status.model_dump(mode="json") for status in ctx.repository.list_camera_statuses()]
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
    ),
    AgentTool(
        name="get_violation_statistics",
        description="汇总已入库的违规数量、类型和严重级别。",
        parameters="query: ViolationQuery",
        handler=_get_violation_statistics,
    ),
    AgentTool(
        name="get_camera_status",
        description="查询一个明确 camera_id 的最新状态。",
        parameters="camera_id: string",
        handler=_get_camera_status,
    ),
    AgentTool(
        name="get_all_camera_statuses",
        description="列出所有已知摄像头的最新状态。",
        parameters="none",
        handler=_get_all_camera_statuses,
    ),
    AgentTool(
        name="get_workforce_summary",
        description="汇总在线摄像头上报的活跃作业人数，不进行跨摄像头人员去重。",
        parameters="none",
        handler=_get_workforce_summary,
    ),
    AgentTool(
        name="get_current_weather",
        description="查询一个明确地点的当前天气。",
        parameters="location: string",
        handler=_get_current_weather,
    ),
)
