"""Behavioural lock for chat tool selection/dispatch (see chat_harness)."""
from __future__ import annotations

import pytest

from chat_harness import EVENT_UUID, FLAG_SETS, REPORT_ID, TRAINING_ID, assert_golden, run_chat

DUE = "2026-10-01T10:00:00+00:00"

# One scripted decision per tool; every tool in ToolName must appear here.
TOOL_SCENARIOS: dict[str, dict] = {
    "query_violations": {"tool_name": "query_violations", "query": {"camera_id": "A01", "limit": 5}, "purpose": "p"},
    "get_violation_statistics": {"tool_name": "get_violation_statistics", "query": {"camera_id": "A01"}, "purpose": "p"},
    "get_camera_status": {"tool_name": "get_camera_status", "camera_id": "A01", "purpose": "p"},
    "get_all_camera_statuses": {"tool_name": "get_all_camera_statuses", "purpose": "p"},
    "get_workforce_summary": {"tool_name": "get_workforce_summary", "purpose": "p"},
    "get_current_weather": {"tool_name": "get_current_weather", "weather_location": "北京", "purpose": "p"},
    "search_knowledge": {"tool_name": "search_knowledge", "knowledge_query": "高处坠落", "top_k": 3, "purpose": "p"},
    "list_standard_catalog": {"tool_name": "list_standard_catalog", "purpose": "p"},
    "create_rectification_task": {"tool_name": "create_rectification_task", "violation_event_uuid": EVENT_UUID, "task_title": "补戴安全帽", "task_owner": "张三", "task_due_at_utc": DUE, "purpose": "p"},
    "update_rectification_task": {"tool_name": "update_rectification_task", "task_id": "t-1", "task_status": "COMPLETED", "purpose": "p"},
    "start_monitoring": {"tool_name": "start_monitoring", "camera_id": "A01", "purpose": "p"},
    "stop_monitoring": {"tool_name": "stop_monitoring", "camera_id": "A01", "purpose": "p"},
    "list_rectification_targets": {"tool_name": "list_rectification_targets", "purpose": "p"},
    "list_monitoring_targets": {"tool_name": "list_monitoring_targets", "selection_action": "stop", "purpose": "p"},
    "get_learning_overview": {"tool_name": "get_learning_overview", "purpose": "p"},
    "get_learning_insights": {"tool_name": "get_learning_insights", "purpose": "p"},
    "list_safety_reports": {"tool_name": "list_safety_reports", "purpose": "p"},
    "get_safety_report": {"tool_name": "get_safety_report", "report_id": REPORT_ID, "purpose": "p"},
    "list_training_tasks": {"tool_name": "list_training_tasks", "purpose": "p"},
    "get_training_task": {"tool_name": "get_training_task", "training_id": TRAINING_ID, "purpose": "p"},
    "get_training_statistics": {"tool_name": "get_training_statistics", "training_id": TRAINING_ID, "purpose": "p"},
    "prepare_training_task": {"tool_name": "prepare_training_task", "purpose": "p"},
    "create_safety_report": {"tool_name": "create_safety_report", "report_period": "THIS_WEEK", "purpose": "p"},
    "update_safety_report": {"tool_name": "update_safety_report", "report_id": REPORT_ID, "report_summary": "新摘要", "purpose": "p"},
    "confirm_safety_report": {"tool_name": "confirm_safety_report", "report_id": REPORT_ID, "purpose": "p"},
    "delete_safety_report": {"tool_name": "delete_safety_report", "report_id": REPORT_ID, "purpose": "p"},
    "create_training_task": {"tool_name": "create_training_task", "report_id": REPORT_ID, "training_title": "培训", "training_target_count": 5, "purpose": "p"},
    "update_training_task": {"tool_name": "update_training_task", "training_id": TRAINING_ID, "training_pass_score": 90, "purpose": "p"},
    "publish_training_task": {"tool_name": "publish_training_task", "training_id": TRAINING_ID, "purpose": "p"},
    "delete_training_task": {"tool_name": "delete_training_task", "training_id": TRAINING_ID, "purpose": "p"},
    "send_feishu_notification": {"tool_name": "send_feishu_notification", "notification_title": "通报", "notification_content": "请注意", "purpose": "p"},
}


def test_every_tool_has_a_scenario() -> None:
    from typing import get_args
    from agent.contracts.chat import ToolName
    assert set(TOOL_SCENARIOS) == set(get_args(ToolName))


@pytest.mark.parametrize("flag_set", sorted(FLAG_SETS))
def test_catalog_offered_to_model(flag_set: str) -> None:
    result = run_chat([None], flags=FLAG_SETS[flag_set])
    assert_golden(f"catalog_{flag_set}", result["model_calls"][0]["catalog"])


@pytest.mark.parametrize("tool", sorted(TOOL_SCENARIOS))
def test_tool_dispatch(tool: str, monkeypatch) -> None:
    result = run_chat([TOOL_SCENARIOS[tool]], flags=FLAG_SETS["full"], monkeypatch=monkeypatch)
    for call in result["model_calls"]:
        call.pop("catalog", None)
    assert_golden(f"tool_{tool}", result)


EDGE_SCENARIOS = {
    "two_step_loop": dict(decisions=[TOOL_SCENARIOS["get_violation_statistics"], TOOL_SCENARIOS["query_violations"]], flags=FLAG_SETS["full"]),
    "max_tool_calls_cap": dict(decisions=[TOOL_SCENARIOS["get_violation_statistics"], TOOL_SCENARIOS["query_violations"]], flags=FLAG_SETS["full"], max_tool_calls=1),
    "no_tool_needed": dict(decisions=[None], flags=FLAG_SETS["full"]),
    "write_action_rejected": dict(decisions=[TOOL_SCENARIOS["start_monitoring"]], flags=FLAG_SETS["full"], write_fails=True),
    "write_disabled": dict(decisions=[TOOL_SCENARIOS["start_monitoring"]], flags=FLAG_SETS["none"]),
    "knowledge_disabled": dict(decisions=[TOOL_SCENARIOS["search_knowledge"]], flags=FLAG_SETS["none"]),
    "catalog_disabled": dict(decisions=[TOOL_SCENARIOS["list_standard_catalog"]], flags=FLAG_SETS["none"]),
    "learning_disabled_read": dict(decisions=[TOOL_SCENARIOS["list_safety_reports"]], flags=FLAG_SETS["none"]),
    "learning_disabled_prepare": dict(decisions=[TOOL_SCENARIOS["prepare_training_task"]], flags=FLAG_SETS["none"]),
    "notification_disabled": dict(decisions=[TOOL_SCENARIOS["send_feishu_notification"]], flags=FLAG_SETS["none"]),
    "model_decision_error": dict(decisions=[RuntimeError("boom")], flags=FLAG_SETS["full"]),
    "unsupported_standard_reference": dict(decisions=[None], flags=FLAG_SETS["full"], answer="依据 GB 99999-2020 第9条执行"),
    "camera_not_found": dict(decisions=[{"tool_name": "get_camera_status", "camera_id": "ZZ9", "purpose": "p"}], flags=FLAG_SETS["full"]),
    "reports_then_detail": dict(decisions=[TOOL_SCENARIOS["list_safety_reports"], TOOL_SCENARIOS["get_safety_report"]], flags=FLAG_SETS["full"]),
}


@pytest.mark.parametrize("name", sorted(EDGE_SCENARIOS))
def test_edge_cases(name: str, monkeypatch) -> None:
    result = run_chat(monkeypatch=monkeypatch, **EDGE_SCENARIOS[name])
    for call in result["model_calls"]:
        call.pop("catalog", None)
    assert_golden(f"edge_{name}", result)
