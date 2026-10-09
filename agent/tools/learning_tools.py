from __future__ import annotations

from agent.services.learning_service import LearningService
from .registry import ToolRegistry


def register_learning_tools(registry: ToolRegistry, learning: LearningService) -> None:
    registry.register(
        "get_learning_overview", lambda: learning.weekly_overview(),
        description="快速查询本周安全教育统计、主要风险及培训完成情况。", parameters="无",
    )
    registry.register(
        "get_learning_insights", lambda: learning.weekly_insights(),
        description="查询本周风险关联的推荐事故案例和 AI 教育建议；建议短期复用。", parameters="无",
    )
    registry.register(
        "list_safety_reports",
        lambda: [{"report_id": row.report_id, "period_start_utc": row.period_start_utc.isoformat(),
                  "period_end_utc": row.period_end_utc.isoformat(), "status": row.status,
                  "event_count": row.statistics.get("total", 0), "summary": row.content.summary[:300],
                  "pdf_url": row.pdf_url} for row in learning.list_reports()],
        description="列出安全报告，返回真实报告 ID、统计周期、状态、摘要和 PDF 地址；选择报告前先调用。", parameters="无",
    )
    registry.register(
        "get_safety_report", lambda report_id: learning.get_report(report_id).model_dump(mode="json"),
        description="读取指定安全报告的统计、正文与规范引用。", parameters="report_id: string",
    )
    registry.register(
        "list_training_tasks",
        lambda: [{"training_id": row.task_id, "report_id": row.report_id, "title": row.title,
                  "status": row.status, "target_count": row.target_count, "question_count": row.question_count,
                  "material_preview": row.material[:300], "public_url": row.public_url}
                 for row in learning.list_training()],
        description="列出培训任务及其真实 ID、来源报告、标题、状态、人数和学习材料摘要；选择任务前先调用。", parameters="无",
    )
    registry.register(
        "get_training_task", lambda training_id: learning.get_training(training_id).model_dump(mode="json"),
        description="读取培训材料、题目、来源文档、学习地址和任务状态。", parameters="training_id: string",
    )
    registry.register(
        "get_training_statistics", lambda training_id: _training_statistics(learning, training_id),
        description="查询培训目标人数、完成人数、完成率、平均分、及格率与最近 20 条答题记录。", parameters="training_id: string",
    )


def _training_statistics(learning: LearningService, training_id: str) -> dict:
    statistics = learning.training_statistics(training_id)
    submissions = statistics["submissions"]
    return {**statistics, "submission_count": len(submissions), "submissions": submissions[:20]}
