from __future__ import annotations

from agent.contracts.chat import ToolDecision
from agent.contracts.query import ViolationQuery
from agent.tools.base import AgentTool, Capability, ToolContext, ToolOutcome


_DEFAULT_NOTIFICATION_DESCRIPTION = (
    "向施工安全管理飞书群发送安全通报或风险简报卡片；当用户明确要求推送/通知飞书群时调用。"
)


def _resolve_target_label(ctx: ToolContext) -> str:
    info = ctx.describe_notification_channels()
    labels = info.get("labels") or []
    if labels:
        return "、".join(labels)
    # Preserve default phrasing for minimal BriefingNotificationPort stubs lacking channel metadata.
    return "飞书安全管理群"


def _notification_context_keywords(ctx: ToolContext) -> tuple[str, ...]:
    info = ctx.describe_notification_channels()
    return tuple(info.get("aliases") or ())


def _resolve_notification_description(ctx: ToolContext) -> str:
    info = ctx.describe_notification_channels()
    channels = info.get("channels") or []
    labels = info.get("labels") or []
    if not labels or channels == ["feishu"]:
        return _DEFAULT_NOTIFICATION_DESCRIPTION
    return f"向已配置通知通道（{'、'.join(labels)}）发送安全通报或风险简报卡片；当用户明确要求推送/通知时调用。"


def _send_feishu_notification(decision: ToolDecision, ctx: ToolContext) -> ToolOutcome:
    if ctx.notification_service is None or not ctx.notification_service.is_configured:
        raise RuntimeError("notification service is not configured")
    stats = ctx.repository.get_statistics(ViolationQuery(limit=20))
    title = (decision.notification_title or "施工现场安全态势通报").strip()
    custom_body = (decision.notification_content or "").strip()
    summary_md = (
        f"{custom_body}\n\n" if custom_body else ""
    ) + (
        f"**📊 现场实时统计快照**：\n"
        f"- 累计记录违规事件：**{stats.total_violations}** 起\n"
        f"- 严重告警 (CRITICAL)：**{stats.by_severity.get('CRITICAL', 0)}** 起\n"
        f"- 风险预警 (WARNING)：**{stats.by_severity.get('WARNING', 0)}** 起\n"
        f"- 平均持续时长：**{stats.average_duration_seconds:.1f}** 秒"
    )
    target_label = _resolve_target_label(ctx)
    send_res = ctx.notification_service.send_custom_briefing(title, summary_md, sync=True)
    ok = isinstance(send_res, dict) and bool(send_res.get("ok"))
    answer = (
        f"已将《{title}》互动卡片推送至{target_label}。"
        if ok
        else f"{target_label}消息推送未完成，请检查通道配置或网络连接。"
    )
    return ToolOutcome(data=send_res, success=ok, answer=answer, citations=[])


NOTIFICATION_TOOLS: tuple[AgentTool, ...] = (
    AgentTool(
        name="send_feishu_notification",
        description=_DEFAULT_NOTIFICATION_DESCRIPTION,
        parameters="可选 notification_title, notification_content",
        handler=_send_feishu_notification,
        requires=frozenset({Capability.NOTIFICATION}),
        intent_keywords=("通知", "推送", "通报", "简报", "播报", "告警群", "发群", "群消息"),
        context_keywords=_notification_context_keywords,
        description_resolver=_resolve_notification_description,
    ),
)
