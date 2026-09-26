from __future__ import annotations

from agent.contracts.query import ViolationQuery
from agent.repositories.violations import ViolationRepository
from .registry import ToolRegistry
from .weather import get_current_weather


def register_safety_tools(repository: ViolationRepository) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register("query_violations", lambda query: [item.model_dump(mode="json") for item in repository.query_events(ViolationQuery.model_validate(query))], description="查询已入库的违规事件明细。", parameters="query: ViolationQuery")
    registry.register("get_violation_statistics", lambda query: repository.get_statistics(ViolationQuery.model_validate(query)).model_dump(mode="json"), description="汇总已入库的违规数量、类型和严重级别。", parameters="query: ViolationQuery")
    registry.register("get_camera_status", lambda camera_id: (status.model_dump(mode="json") if (status := repository.get_camera_status(camera_id)) else None), description="查询一个明确 camera_id 的最新状态。", parameters="camera_id: string")
    registry.register("get_all_camera_statuses", lambda: [status.model_dump(mode="json") for status in repository.list_camera_statuses()], description="列出所有已知摄像头的最新状态。", parameters="none")
    registry.register("get_workforce_summary", lambda: repository.get_workforce_summary(), description="汇总在线摄像头上报的活跃作业人数，不进行跨摄像头人员去重。", parameters="none")
    registry.register("get_current_weather", lambda location: get_current_weather(location).model_dump(mode="json"), description="查询一个明确地点的当前天气。", parameters="location: string")
    return registry
