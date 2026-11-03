from __future__ import annotations

from agent.contracts.actions import GuidedSelection, GuidedSelectionOption
from agent.contracts.chat import Evidence, ToolDecision
from agent.contracts.event_v1 import EventStatus
from agent.contracts.query import ViolationQuery
from agent.tools.base import AgentTool, Capability, ToolContext, ToolOutcome


def _list_rectification_targets(_decision: ToolDecision, ctx: ToolContext) -> ToolOutcome:
    events = ctx.repository.query_events(ViolationQuery(status=EventStatus.ACTIVE, limit=8))
    options = [
        GuidedSelectionOption(
            option_id=event.event_uuid,
            label=f"{event.violation_type} · {event.camera_id}",
            description=f"{event.occurred_at_utc.strftime('%Y-%m-%d %H:%M UTC')} · {event.severity} · {event.event_uuid[:8]}",
        )
        for event in events
    ]
    selection = GuidedSelection(
        kind="RECTIFICATION_TARGET",
        prompt="请选择需要创建整改任务的活动违规；选中后填写整改要求、负责人和截止时间。" if options else "当前没有可创建整改任务的活动违规。",
        options=options,
    )
    evidence = [
        Evidence(event_uuid=item.event_uuid, occurred_at_utc=item.occurred_at_utc, snapshot_uri=item.snapshot_uri)
        for item in events
    ]
    return ToolOutcome(
        data=selection.model_dump(mode="json"),
        guided_selection=selection,
        evidence=evidence,
        citations=[],
    )


def _list_monitoring_targets(decision: ToolDecision, ctx: ToolContext) -> ToolOutcome:
    action = decision.selection_action
    assert action is not None
    cameras = ctx.repository.list_managed_cameras()
    verb = "停止" if action == "stop" else "启动"
    selection = GuidedSelection(
        kind="CAMERA_TARGET",
        prompt=f"请选择要{verb}监控的摄像头；选择后仍会显示确认卡片，不会立即执行。" if cameras else "当前没有已登记的摄像头可供操作。",
        options=[
            GuidedSelectionOption(
                option_id=camera.camera_id,
                label=f"{camera.display_name}（{camera.camera_id}）",
                description=f"当前期望状态：{camera.desired_state}",
                follow_up_question=f"{verb} {camera.camera_id} 监控",
            )
            for camera in cameras
        ],
    )
    return ToolOutcome(
        data=selection.model_dump(mode="json"),
        guided_selection=selection,
        citations=[],
    )


def _prepare_training_task(_decision: ToolDecision, ctx: ToolContext) -> ToolOutcome:
    if not ctx.learning_service:
        raise RuntimeError("learning service is disabled")
    reports = [report for report in ctx.learning_service.list_reports() if report.status == "CONFIRMED"]
    options = [
        GuidedSelectionOption(
            option_id=report.report_id,
            label=f"{report.period_start_utc.date()} 至 {report.period_end_utc.date()} 安全报告",
            description=f"违规事件 {report.statistics.get('total', 0)} 起 · {report.content.summary[:72]}",
        )
        for report in reports[:10]
    ]
    selection = GuidedSelection(
        kind="TRAINING_REPORT",
        prompt="请选择一份已确认的安全报告，再填写培训主题和目标人数。" if options else "当前没有已确认的安全报告。请先生成并确认报告，然后再创建培训任务。",
        options=options,
    )
    return ToolOutcome(
        data=selection.model_dump(mode="json"),
        guided_selection=selection,
        citations=[],
    )


_REQ_WRITE = frozenset({Capability.WRITE})
_REQ_LEARNING_WRITE = frozenset({Capability.LEARNING, Capability.WRITE})

LIST_RECTIFICATION_TARGETS_TOOL = AgentTool(
    name="list_rectification_targets",
    description="只读列出可创建整改任务的活动违规，供页面选择目标。",
    parameters="无",
    handler=_list_rectification_targets,
    requires=_REQ_WRITE,
)

LIST_MONITORING_TARGETS_TOOL = AgentTool(
    name="list_monitoring_targets",
    description="只读列出可启停监控的已登记摄像头，供页面选择目标。",
    parameters="selection_action: start | stop",
    handler=_list_monitoring_targets,
    requires=_REQ_WRITE,
)

PREPARE_TRAINING_TASK_TOOL = AgentTool(
    name="prepare_training_task",
    description="用户要生成培训，但尚未给出已确认报告、标题或目标人数时，只读列出可选报告并引导页面收集信息。",
    parameters="无",
    handler=_prepare_training_task,
    requires=_REQ_LEARNING_WRITE,
)
