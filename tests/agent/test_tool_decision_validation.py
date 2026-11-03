"""Characterization tests for ToolDecision.enforce_tool_boundaries.

Error message substrings are fed back into the LLM retry prompt on validation
failure, so they must remain stable across the table-driven refactor in P2.
"""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from agent.contracts.chat import ToolDecision

BASE = {"purpose": "测试目的"}


@pytest.mark.parametrize(
    ("payload", "expected_message"),
    [
        (
            {"tool_name": "query_violations", "query": {"limit": 101}},
            "chat tools may request at most 100 records",
        ),
        (
            {
                "tool_name": "query_violations",
                "query": {
                    "start_time_utc": "2026-10-10T00:00:00Z",
                    "end_time_utc": "2026-10-09T00:00:00Z",
                },
            },
            "end_time_utc must not precede start_time_utc",
        ),
        (
            {
                "tool_name": "query_violations",
                "query": {
                    "start_time_utc": "2026-08-01T00:00:00Z",
                    "end_time_utc": "2026-09-10T00:00:00Z",
                },
            },
            "chat tool time range may not exceed 31 days",
        ),
        (
            {"tool_name": "get_camera_status"},
            "camera_id is required for get_camera_status",
        ),
        (
            {"tool_name": "get_current_weather"},
            "weather_location is required for get_current_weather",
        ),
        (
            {"tool_name": "search_knowledge"},
            "knowledge_query is required for search_knowledge",
        ),
        (
            {"tool_name": "create_rectification_task", "task_title": "整改"},
            "violation_event_uuid, task_title, task_owner and task_due_at_utc are required for create_rectification_task",
        ),
        (
            {"tool_name": "update_rectification_task", "task_status": "COMPLETED"},
            "task_id is required for update_rectification_task",
        ),
        (
            {"tool_name": "update_rectification_task", "task_id": "t-1"},
            "at least one task update is required",
        ),
        (
            {"tool_name": "start_monitoring"},
            "camera_id is required for monitoring control",
        ),
        (
            {"tool_name": "stop_monitoring"},
            "camera_id is required for monitoring control",
        ),
        (
            {"tool_name": "list_monitoring_targets"},
            "selection_action is required for list_monitoring_targets",
        ),
        (
            {
                "tool_name": "create_safety_report",
                "report_period_start_utc": "2026-10-01T00:00:00Z",
            },
            "report start and end must be provided together",
        ),
        (
            {
                "tool_name": "create_safety_report",
                "report_period_start_utc": "2026-10-05T00:00:00Z",
                "report_period_end_utc": "2026-10-01T00:00:00Z",
            },
            "report end must be after start",
        ),
        (
            {"tool_name": "get_safety_report"},
            "report_id is required",
        ),
        (
            {"tool_name": "update_safety_report"},
            "report_id is required",
        ),
        (
            {"tool_name": "confirm_safety_report"},
            "report_id is required",
        ),
        (
            {"tool_name": "delete_safety_report"},
            "report_id is required",
        ),
        (
            {"tool_name": "update_safety_report", "report_id": "r-1"},
            "at least one report content field is required",
        ),
        (
            {"tool_name": "get_training_task"},
            "training_id is required",
        ),
        (
            {"tool_name": "get_training_statistics"},
            "training_id is required",
        ),
        (
            {"tool_name": "update_training_task"},
            "training_id is required",
        ),
        (
            {"tool_name": "publish_training_task"},
            "training_id is required",
        ),
        (
            {"tool_name": "delete_training_task"},
            "training_id is required",
        ),
        (
            {"tool_name": "create_training_task", "report_id": "r-1"},
            "report_id, training_title, training_target_count are required",
        ),
        (
            {"tool_name": "update_training_task", "training_id": "t-1"},
            "at least one training change is required",
        ),
    ],
)
def test_tool_decision_rejects_invalid_payloads(payload: dict, expected_message: str) -> None:
    with pytest.raises(ValidationError) as exc_info:
        ToolDecision.model_validate({**BASE, **payload})
    assert expected_message in str(exc_info.value)


def test_tool_decision_accepts_valid_payloads() -> None:
    d1 = ToolDecision.model_validate({
        **BASE,
        "tool_name": "create_safety_report",
        "report_period_start_utc": "2026-10-01T00:00:00Z",
        "report_period_end_utc": "2026-10-07T00:00:00Z",
    })
    assert d1.tool_name == "create_safety_report"

    d2 = ToolDecision.model_validate({
        **BASE,
        "tool_name": "update_training_task",
        "training_id": "t-1",
        "training_pass_score": 0,
    })
    assert d2.training_pass_score == 0
