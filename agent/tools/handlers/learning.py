from __future__ import annotations

from agent.contracts.chat import ToolDecision
from agent.domain.time_context import (
    enrich_record_local_times,
    enrich_records_local_times,
    resolve_context_timezone,
)
from agent.tools.base import AgentTool, Capability, ToolContext, ToolOutcome

_PERIOD_TIME_FIELDS = (
    ("period_start_utc", "period_start_local"),
    ("period_end_utc", "period_end_local"),
    ("created_at_utc", "created_at_local"),
)
_INSIGHTS_TIME_FIELDS = (
    ("period_start_utc", "period_start_local"),
    ("generated_at_utc", "generated_at_local"),
)
_SUBMISSION_TIME_FIELDS = (("submitted_at_utc", "submitted_at_local"),)


def _require_learning(ctx: ToolContext):
    if ctx.learning_service is None:
        raise RuntimeError("learning service is disabled")
    return ctx.learning_service


def _get_learning_overview(_decision: ToolDecision, ctx: ToolContext) -> ToolOutcome:
    tz = resolve_context_timezone(ctx)
    data = enrich_record_local_times(_require_learning(ctx).weekly_overview(), _PERIOD_TIME_FIELDS, tz)
    return ToolOutcome(data=data)


def _get_learning_insights(_decision: ToolDecision, ctx: ToolContext) -> ToolOutcome:
    tz = resolve_context_timezone(ctx)
    data = enrich_record_local_times(_require_learning(ctx).weekly_insights(), _INSIGHTS_TIME_FIELDS, tz)
    return ToolOutcome(data=data)


def _list_safety_reports(_decision: ToolDecision, ctx: ToolContext) -> ToolOutcome:
    learning = _require_learning(ctx)
    tz = resolve_context_timezone(ctx)
    data = [
        enrich_record_local_times(
            {
                "report_id": row.report_id,
                "period_start_utc": row.period_start_utc.isoformat(),
                "period_end_utc": row.period_end_utc.isoformat(),
                "status": row.status,
                "event_count": row.statistics.get("total", 0),
                "summary": row.content.summary[:300],
                "pdf_url": row.pdf_url,
            },
            _PERIOD_TIME_FIELDS,
            tz,
        )
        for row in learning.list_reports()
    ]
    return ToolOutcome(data=data)


def _get_safety_report(decision: ToolDecision, ctx: ToolContext) -> ToolOutcome:
    learning = _require_learning(ctx)
    tz = resolve_context_timezone(ctx)
    raw = learning.get_report(decision.report_id or "").model_dump(mode="json")
    return ToolOutcome(data=enrich_record_local_times(raw, _PERIOD_TIME_FIELDS, tz))


def _list_training_tasks(_decision: ToolDecision, ctx: ToolContext) -> ToolOutcome:
    learning = _require_learning(ctx)
    data = [
        {
            "training_id": row.task_id,
            "report_id": row.report_id,
            "title": row.title,
            "status": row.status,
            "target_count": row.target_count,
            "question_count": row.question_count,
            "material_preview": row.material[:300],
            "public_url": row.public_url,
        }
        for row in learning.list_training()
    ]
    return ToolOutcome(data=data)


def _get_training_task(decision: ToolDecision, ctx: ToolContext) -> ToolOutcome:
    learning = _require_learning(ctx)
    return ToolOutcome(data=learning.get_training(decision.training_id or "").model_dump(mode="json"))


def _get_training_statistics(decision: ToolDecision, ctx: ToolContext) -> ToolOutcome:
    learning = _require_learning(ctx)
    tz = resolve_context_timezone(ctx)
    statistics = learning.training_statistics(decision.training_id or "")
    submissions = enrich_records_local_times(statistics["submissions"], _SUBMISSION_TIME_FIELDS, tz)
    data = {**statistics, "submission_count": len(submissions), "submissions": submissions[:20]}
    return ToolOutcome(data=data)


def _summarize_safety_reports(data: object) -> str:
    count = len(data) if isinstance(data, list) else 0
    return f"当前查询到 {count} 份安全报告。可在下方预览摘要、查看详情或打开 PDF。" if count else "当前没有安全报告。"


def _summarize_training_tasks(data: object) -> str:
    count = len(data) if isinstance(data, list) else 0
    return f"当前查询到 {count} 项培训任务。可在下方预览内容、查看详情或打开学习页。" if count else "当前没有培训任务。"


_REQ_LEARNING = frozenset({Capability.LEARNING})

LEARNING_READ_TOOLS: tuple[AgentTool, ...] = (
    AgentTool(
        name="get_learning_overview",
        description="快速查询本周安全教育统计、主要风险及培训完成情况。",
        parameters="无",
        handler=_get_learning_overview,
        requires=_REQ_LEARNING,
        intent_keywords=("报告", "周报", "培训", "学习", "教育"),
    ),
    AgentTool(
        name="get_learning_insights",
        description="查询本周风险关联的推荐事故案例和 AI 教育建议；建议短期复用。",
        parameters="无",
        handler=_get_learning_insights,
        requires=_REQ_LEARNING,
        intent_keywords=("报告", "周报", "培训", "学习", "建议", "教育"),
    ),
    AgentTool(
        name="list_safety_reports",
        description="列出安全报告，返回真实报告 ID、统计周期、状态、摘要和 PDF 地址；选择报告前先调用。",
        parameters="无",
        handler=_list_safety_reports,
        requires=_REQ_LEARNING,
        terminal_summary=_summarize_safety_reports,
        intent_keywords=("报告", "周报", "安全报告", "pdf"),
    ),
    AgentTool(
        name="get_safety_report",
        description="读取指定安全报告的统计、正文与规范引用。",
        parameters="report_id: string",
        handler=_get_safety_report,
        requires=_REQ_LEARNING,
        intent_keywords=("报告", "周报", "安全报告", "pdf"),
    ),
    AgentTool(
        name="list_training_tasks",
        description="列出培训任务及其真实 ID、来源报告、标题、状态、人数和学习材料摘要；选择任务前先调用。",
        parameters="无",
        handler=_list_training_tasks,
        requires=_REQ_LEARNING,
        terminal_summary=_summarize_training_tasks,
        intent_keywords=("培训", "学习", "答题", "考试", "教育"),
    ),
    AgentTool(
        name="get_training_task",
        description="读取培训材料、题目、来源文档、学习地址和任务状态。",
        parameters="training_id: string",
        handler=_get_training_task,
        requires=_REQ_LEARNING,
        intent_keywords=("培训", "学习", "答题", "考试", "教育"),
    ),
    AgentTool(
        name="get_training_statistics",
        description="查询培训目标人数、完成人数、完成率、平均分、及格率与最近 20 条答题记录。",
        parameters="training_id: string",
        handler=_get_training_statistics,
        requires=_REQ_LEARNING,
        intent_keywords=("培训", "学习", "答题", "考试", "教育", "成绩"),
    ),
)
