from __future__ import annotations

from agent.contracts.chat import ToolDecision
from agent.tools.base import AgentTool, Capability, ToolContext, ToolOutcome


def _require_learning(ctx: ToolContext):
    if ctx.learning_service is None:
        raise RuntimeError("learning service is disabled")
    return ctx.learning_service


def _get_learning_overview(_decision: ToolDecision, ctx: ToolContext) -> ToolOutcome:
    return ToolOutcome(data=_require_learning(ctx).weekly_overview())


def _get_learning_insights(_decision: ToolDecision, ctx: ToolContext) -> ToolOutcome:
    return ToolOutcome(data=_require_learning(ctx).weekly_insights())


def _list_safety_reports(_decision: ToolDecision, ctx: ToolContext) -> ToolOutcome:
    learning = _require_learning(ctx)
    data = [
        {
            "report_id": row.report_id,
            "period_start_utc": row.period_start_utc.isoformat(),
            "period_end_utc": row.period_end_utc.isoformat(),
            "status": row.status,
            "event_count": row.statistics.get("total", 0),
            "summary": row.content.summary[:300],
            "pdf_url": row.pdf_url,
        }
        for row in learning.list_reports()
    ]
    return ToolOutcome(data=data)


def _get_safety_report(decision: ToolDecision, ctx: ToolContext) -> ToolOutcome:
    learning = _require_learning(ctx)
    return ToolOutcome(data=learning.get_report(decision.report_id or "").model_dump(mode="json"))


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
    statistics = learning.training_statistics(decision.training_id or "")
    submissions = statistics["submissions"]
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
    ),
    AgentTool(
        name="get_learning_insights",
        description="查询本周风险关联的推荐事故案例和 AI 教育建议；建议短期复用。",
        parameters="无",
        handler=_get_learning_insights,
        requires=_REQ_LEARNING,
    ),
    AgentTool(
        name="list_safety_reports",
        description="列出安全报告，返回真实报告 ID、统计周期、状态、摘要和 PDF 地址；选择报告前先调用。",
        parameters="无",
        handler=_list_safety_reports,
        requires=_REQ_LEARNING,
        terminal_summary=_summarize_safety_reports,
    ),
    AgentTool(
        name="get_safety_report",
        description="读取指定安全报告的统计、正文与规范引用。",
        parameters="report_id: string",
        handler=_get_safety_report,
        requires=_REQ_LEARNING,
    ),
    AgentTool(
        name="list_training_tasks",
        description="列出培训任务及其真实 ID、来源报告、标题、状态、人数和学习材料摘要；选择任务前先调用。",
        parameters="无",
        handler=_list_training_tasks,
        requires=_REQ_LEARNING,
        terminal_summary=_summarize_training_tasks,
    ),
    AgentTool(
        name="get_training_task",
        description="读取培训材料、题目、来源文档、学习地址和任务状态。",
        parameters="training_id: string",
        handler=_get_training_task,
        requires=_REQ_LEARNING,
    ),
    AgentTool(
        name="get_training_statistics",
        description="查询培训目标人数、完成人数、完成率、平均分、及格率与最近 20 条答题记录。",
        parameters="training_id: string",
        handler=_get_training_statistics,
        requires=_REQ_LEARNING,
    ),
)
