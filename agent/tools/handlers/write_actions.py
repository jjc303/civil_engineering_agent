from __future__ import annotations

from agent.contracts.chat import ToolDecision
from agent.tools.base import AgentTool, Capability, ToolContext, ToolOutcome
from agent.tools.handlers.guided import (
    LIST_MONITORING_TARGETS_TOOL,
    LIST_RECTIFICATION_TARGETS_TOOL,
    PREPARE_TRAINING_TASK_TOOL,
)


def _propose_write_action(decision: ToolDecision, ctx: ToolContext) -> ToolOutcome:
    if not ctx.write_action_service:
        raise RuntimeError("write actions are disabled")
    pending = ctx.write_action_service.propose(ctx.conversation_id, decision)
    return ToolOutcome(
        data=pending.model_dump(mode="json"),
        pending_action=pending,
        citations=[],
    )


_REQ_WRITE = frozenset({Capability.WRITE})
_REQ_LEARNING_WRITE = frozenset({Capability.LEARNING, Capability.WRITE})

CORE_WRITE_TOOLS: tuple[AgentTool, ...] = (
    AgentTool(
        name="create_rectification_task",
        description="生成待确认的整改任务；必须给出违规事件 ID、标题、负责人和 UTC 截止时间。",
        parameters="violation_event_uuid, task_title, task_description, task_owner, task_due_at_utc",
        handler=_propose_write_action,
        requires=_REQ_WRITE,
    ),
    AgentTool(
        name="update_rectification_task",
        description="生成待确认的整改任务更新；完成任务会把关联违规标为已解决。",
        parameters="task_id, task_owner, task_due_at_utc, task_status, task_note",
        handler=_propose_write_action,
        requires=_REQ_WRITE,
    ),
    AgentTool(
        name="start_monitoring",
        description="生成待确认的摄像头监控启动操作。",
        parameters="camera_id",
        handler=_propose_write_action,
        requires=_REQ_WRITE,
    ),
    AgentTool(
        name="stop_monitoring",
        description="生成待确认的摄像头监控停止操作。",
        parameters="camera_id",
        handler=_propose_write_action,
        requires=_REQ_WRITE,
    ),
    LIST_RECTIFICATION_TARGETS_TOOL,
    LIST_MONITORING_TARGETS_TOOL,
)

LEARNING_WRITE_TOOLS: tuple[AgentTool, ...] = (
    AgentTool(
        name="create_safety_report",
        description="生成安全报告草稿，写操作需页面确认。未指定周期时服务端默认本周；指定其他周期时提供明确 UTC 起止时间。",
        parameters="可选 report_period=THIS_WEEK 或 report_period_start_utc, report_period_end_utc",
        handler=_propose_write_action,
        requires=_REQ_LEARNING_WRITE,
    ),
    AgentTool(
        name="update_safety_report",
        description="修改尚未确认的报告正文，写操作需页面确认。",
        parameters="report_id 及 report_summary, report_risk_analysis, report_remediation 中至少一项",
        handler=_propose_write_action,
        requires=_REQ_LEARNING_WRITE,
    ),
    AgentTool(
        name="confirm_safety_report",
        description="确认报告并生成 PDF，写操作需页面确认。",
        parameters="report_id",
        handler=_propose_write_action,
        requires=_REQ_LEARNING_WRITE,
    ),
    AgentTool(
        name="delete_safety_report",
        description="删除报告及 PDF；如已关联培训需先删除培训。写操作需页面确认。",
        parameters="report_id",
        handler=_propose_write_action,
        requires=_REQ_LEARNING_WRITE,
    ),
    AgentTool(
        name="create_training_task",
        description="基于已确认报告及选中的案例、规范生成培训材料与题目草稿，写操作需页面确认。",
        parameters="report_id, training_title, training_target_count；可选 training_document_ids, training_question_count, training_pass_score",
        handler=_propose_write_action,
        requires=_REQ_LEARNING_WRITE,
    ),
    PREPARE_TRAINING_TASK_TOOL,
    AgentTool(
        name="update_training_task",
        description="修改培训草稿的标题、目标人数、及格分、材料或题目，写操作需页面确认。",
        parameters="training_id；training_title, training_target_count, training_pass_score, training_material, training_questions 至少一项",
        handler=_propose_write_action,
        requires=_REQ_LEARNING_WRITE,
    ),
    AgentTool(
        name="publish_training_task",
        description="发布培训任务并生成学习链接和二维码，写操作需页面确认。",
        parameters="training_id",
        handler=_propose_write_action,
        requires=_REQ_LEARNING_WRITE,
    ),
    AgentTool(
        name="delete_training_task",
        description="删除培训任务及已有答题成绩，链接和二维码随之失效，写操作需页面确认。",
        parameters="training_id",
        handler=_propose_write_action,
        requires=_REQ_LEARNING_WRITE,
    ),
)
