from __future__ import annotations

from agent.contracts.query import ViolationQuery
from agent.repositories.violations import ViolationRepository
from .registry import ToolRegistry
from .weather import get_current_weather


def register_safety_tools(repository: ViolationRepository) -> ToolRegistry:
    registry = ToolRegistry()
    registry.register("query_violations", lambda query: [item.model_dump(mode="json") for item in repository.query_events(ViolationQuery.model_validate(query))])
    registry.register("get_violation_statistics", lambda query: repository.get_statistics(ViolationQuery.model_validate(query)).model_dump(mode="json"))
    registry.register("get_camera_status", lambda camera_id: (status.model_dump(mode="json") if (status := repository.get_camera_status(camera_id)) else None))
    registry.register("get_current_weather", lambda location: get_current_weather(location).model_dump(mode="json"))
    return registry
