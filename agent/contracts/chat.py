from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator

from .actions import GuidedSelection, PendingActionResponse
from .query import ViolationQuery
from .learning import TrainingQuestion


ToolName = Literal[
    "query_violations", "get_violation_statistics", "get_camera_status",
    "get_all_camera_statuses", "get_workforce_summary", "get_current_weather", "search_knowledge", "list_standard_catalog",
    "create_rectification_task", "update_rectification_task", "start_monitoring", "stop_monitoring",
    "list_rectification_targets", "list_monitoring_targets",
    "get_learning_overview", "get_learning_insights", "list_safety_reports", "get_safety_report",
    "list_training_tasks", "get_training_task", "get_training_statistics", "prepare_training_task",
    "create_safety_report", "update_safety_report", "confirm_safety_report", "delete_safety_report",
    "create_training_task", "update_training_task", "publish_training_task", "delete_training_task",
    "send_feishu_notification",
]


class ChatRequest(BaseModel):
    question: str = Field(min_length=1, max_length=2000)
    conversation_id: str | None = Field(default=None, max_length=128)

    @field_validator("question")
    @classmethod
    def question_must_not_be_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("question must not be blank")
        return value.strip()


class ToolDecision(BaseModel):
    """The only model output allowed to reach tool execution."""

    tool_name: ToolName
    query: ViolationQuery = Field(default_factory=lambda: ViolationQuery(limit=20))
    camera_id: str | None = Field(default=None, max_length=128)
    weather_location: str | None = Field(default=None, min_length=2, max_length=128)
    knowledge_query: str | None = Field(default=None, min_length=1, max_length=1000)
    top_k: int = Field(default=4, ge=1, le=8)
    violation_event_uuid: str | None = Field(default=None, max_length=36)
    task_id: str | None = Field(default=None, max_length=36)
    task_title: str | None = Field(default=None, min_length=1, max_length=255)
    task_description: str | None = Field(default=None, max_length=4000)
    task_owner: str | None = Field(default=None, min_length=1, max_length=128)
    task_due_at_utc: datetime | None = None
    task_status: Literal["PENDING", "IN_PROGRESS", "COMPLETED", "CANCELLED"] | None = None
    task_note: str | None = Field(default=None, max_length=2000)
    selection_action: Literal["start", "stop"] | None = None
    report_id: str | None = Field(default=None, max_length=36)
    report_period: Literal["THIS_WEEK"] | None = None
    report_period_start_utc: datetime | None = None
    report_period_end_utc: datetime | None = None
    report_summary: str | None = Field(default=None, min_length=1, max_length=10000)
    report_risk_analysis: str | None = Field(default=None, min_length=1, max_length=10000)
    report_remediation: str | None = Field(default=None, min_length=1, max_length=10000)
    training_id: str | None = Field(default=None, max_length=36)
    training_title: str | None = Field(default=None, min_length=1, max_length=255)
    training_document_ids: list[str] | None = Field(default=None, max_length=10)
    training_target_count: int | None = Field(default=None, ge=1)
    training_question_count: int | None = Field(default=None, ge=1, le=20)
    training_pass_score: int | None = Field(default=None, ge=0, le=100)
    training_material: str | None = Field(default=None, min_length=1, max_length=30000)
    training_questions: list[TrainingQuestion] | None = Field(default=None, min_length=1, max_length=20)
    notification_title: str | None = Field(default=None, min_length=1, max_length=128)
    notification_content: str | None = Field(default=None, min_length=1, max_length=4000)
    purpose: str = Field(min_length=1, max_length=256)

    @model_validator(mode="after")
    def enforce_tool_boundaries(self) -> "ToolDecision":
        if self.query.limit > 100:
            raise ValueError("chat tools may request at most 100 records")
        if self.query.start_time_utc and self.query.end_time_utc:
            if self.query.end_time_utc < self.query.start_time_utc:
                raise ValueError("end_time_utc must not precede start_time_utc")
            if (self.query.end_time_utc - self.query.start_time_utc).days > 31:
                raise ValueError("chat tool time range may not exceed 31 days")
        validator = _TOOL_RULES.get(self.tool_name)
        if validator is not None:
            validator(self)
        return self


def _require_camera_id(d: ToolDecision) -> None:
    if not d.camera_id:
        raise ValueError("camera_id is required for get_camera_status")


def _require_monitoring_camera_id(d: ToolDecision) -> None:
    if not d.camera_id:
        raise ValueError("camera_id is required for monitoring control")


def _require_weather_location(d: ToolDecision) -> None:
    if not d.weather_location:
        raise ValueError("weather_location is required for get_current_weather")


def _require_knowledge_query(d: ToolDecision) -> None:
    if not d.knowledge_query:
        raise ValueError("knowledge_query is required for search_knowledge")


def _validate_create_rectification_task(d: ToolDecision) -> None:
    if not all((d.violation_event_uuid, d.task_title, d.task_owner, d.task_due_at_utc)):
        raise ValueError("violation_event_uuid, task_title, task_owner and task_due_at_utc are required for create_rectification_task")


def _validate_update_rectification_task(d: ToolDecision) -> None:
    if not d.task_id:
        raise ValueError("task_id is required for update_rectification_task")
    if not any((d.task_owner, d.task_due_at_utc, d.task_status, d.task_note)):
        raise ValueError("at least one task update is required")


def _require_selection_action(d: ToolDecision) -> None:
    if d.selection_action is None:
        raise ValueError("selection_action is required for list_monitoring_targets")


def _validate_create_safety_report(d: ToolDecision) -> None:
    if bool(d.report_period_start_utc) != bool(d.report_period_end_utc):
        raise ValueError("report start and end must be provided together")
    if d.report_period_start_utc and d.report_period_end_utc and d.report_period_end_utc <= d.report_period_start_utc:
        raise ValueError("report end must be after start")


def _require_report_id(d: ToolDecision) -> None:
    if not d.report_id:
        raise ValueError("report_id is required")


def _validate_update_safety_report(d: ToolDecision) -> None:
    _require_report_id(d)
    if not any((d.report_summary, d.report_risk_analysis, d.report_remediation)):
        raise ValueError("at least one report content field is required")


def _require_training_id(d: ToolDecision) -> None:
    if not d.training_id:
        raise ValueError("training_id is required")


def _validate_create_training_task(d: ToolDecision) -> None:
    if not (d.report_id and d.training_title and d.training_target_count):
        raise ValueError("report_id, training_title, training_target_count are required")


def _validate_update_training_task(d: ToolDecision) -> None:
    _require_training_id(d)
    if not any((d.training_title, d.training_target_count, d.training_pass_score is not None, d.training_material, d.training_questions)):
        raise ValueError("at least one training change is required")


_TOOL_RULES: dict[ToolName, Any] = {
    "get_camera_status": _require_camera_id,
    "get_current_weather": _require_weather_location,
    "search_knowledge": _require_knowledge_query,
    "create_rectification_task": _validate_create_rectification_task,
    "update_rectification_task": _validate_update_rectification_task,
    "start_monitoring": _require_monitoring_camera_id,
    "stop_monitoring": _require_monitoring_camera_id,
    "list_monitoring_targets": _require_selection_action,
    "create_safety_report": _validate_create_safety_report,
    "get_safety_report": _require_report_id,
    "update_safety_report": _validate_update_safety_report,
    "confirm_safety_report": _require_report_id,
    "delete_safety_report": _require_report_id,
    "get_training_task": _require_training_id,
    "get_training_statistics": _require_training_id,
    "create_training_task": _validate_create_training_task,
    "update_training_task": _validate_update_training_task,
    "publish_training_task": _require_training_id,
    "delete_training_task": _require_training_id,
}


class ToolTraceItem(BaseModel):
    tool_name: ToolName
    success: bool
    purpose: str
    duration_ms: int = Field(ge=0)


class Evidence(BaseModel):
    event_uuid: str
    occurred_at_utc: datetime
    snapshot_uri: str | None = None


class KnowledgeCitation(BaseModel):
    document_id: str
    version_no: int
    title: str
    page_or_section: str
    chunk_id: str
    relevance_score: float = Field(ge=0, le=1)
    source_label: str = ""
    document_type: str = "ACCIDENT_REPORT"


class ReportPreview(BaseModel):
    report_id: str
    period_start_utc: datetime
    period_end_utc: datetime
    status: str
    event_count: int = 0
    summary: str = ""
    pdf_url: str | None = None


class TrainingPreview(BaseModel):
    training_id: str
    report_id: str
    title: str
    status: str
    target_count: int
    question_count: int = 0
    material_preview: str = ""
    public_url: str | None = None


class ChatResponse(BaseModel):
    request_id: str
    answer: str
    evidence: list[Evidence] = Field(default_factory=list)
    knowledge_citations: list[KnowledgeCitation] = Field(default_factory=list)
    report_previews: list[ReportPreview] = Field(default_factory=list)
    report_count: int = 0
    training_previews: list[TrainingPreview] = Field(default_factory=list)
    training_count: int = 0
    tool_trace: list[ToolTraceItem] = Field(default_factory=list)
    pending_action: PendingActionResponse | None = None
    guided_selection: GuidedSelection | None = None
    degraded: bool = False
    error_code: str | None = None


class ToolResult(BaseModel):
    tool_name: ToolName
    data: Any
    success: bool = True
