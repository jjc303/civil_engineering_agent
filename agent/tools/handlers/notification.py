from __future__ import annotations

from agent.contracts.chat import ToolDecision
from agent.contracts.query import ViolationQuery
from agent.tools.base import AgentTool, Capability, ToolContext, ToolOutcome


def _send_feishu_notification(decision: ToolDecision, ctx: ToolContext) -> ToolOutcome:
    if not getattr(ctx.notification_service, "is_configured", False):
        raise RuntimeError("feishu notification service is not configured")
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
    send_res = ctx.notification_service.send_custom_briefing(title, summary_md, sync=True)
    ok = bool(send_res and send_res.get("ok"))
    answer = (
        f"已将《{title}》互动卡片推送至飞书安全管理群。"
        if ok
        else "飞书群消息推送未完成，请检查 Webhook 配置或网络连接。"
    )
    return ToolOutcome(data=send_res, success=ok, answer=answer, citations=[])


NOTIFICATION_TOOLS: tuple[AgentTool, ...] = (
    AgentTool(
        name="send_feishu_notification",
        description="向施工安全管理飞书群发送安全通报或风险简报卡片；当用户明确要求推送/通知飞书群时调用。",
        parameters="可选 notification_title, notification_content",
        handler=_send_feishu_notification,
        requires=frozenset({Capability.NOTIFICATION}),
    ),
)
