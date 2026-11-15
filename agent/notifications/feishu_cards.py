"""Feishu Interactive Card renderer with shared layout helpers and configurable links/limits (SRP & OCP)."""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from agent.contracts.learning import ReportResponse, TrainingResponse
from agent.contracts.query import ViolationRecord
from agent.domain.violation_catalog import (
    SEVERITY_DETAILED_LABELS,
    VIOLATION_LABELS,
    get_standard_hint,
)
from .links import DEFAULT_WEB_BASE_URL, NotificationLinkBuilder

SEVERITY_TEMPLATES: dict[str, str] = {
    "CRITICAL": "red",
    "WARNING": "orange",
    "INFO": "blue",
}


@dataclass(frozen=True)
class FeishuCardConfig:
    """Configurable visual, timezone, and truncation limits for Feishu cards."""

    brand_name: str = "智慧施工安全智能体"
    timezone_name: str = "Asia/Shanghai"
    summary_max_chars: int = 200
    remediation_max_chars: int = 160
    material_preview_max_chars: int = 150
    standard_hint_overrides: Mapping[str, str] | None = None


def format_local_time(dt: datetime | str | None, timezone_name: str = "Asia/Shanghai") -> str:
    """Format a UTC datetime or ISO-8601 string into the configured local timezone."""
    if dt is None:
        return "-"
    if isinstance(dt, str):
        try:
            dt = datetime.fromisoformat(dt.replace("Z", "+00:00"))
        except ValueError:
            return dt
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    try:
        tz = ZoneInfo(timezone_name)
    except Exception:
        tz = timezone.utc
    return dt.astimezone(tz).strftime("%Y-%m-%d %H:%M:%S")


def _truncate_text(text: str | None, fallback: str, max_chars: int) -> str:
    cleaned = (text or "").strip() or fallback
    if max_chars > 0 and len(cleaned) > max_chars:
        return cleaned[:max_chars] + "..."
    return cleaned


def _fields_div(items: Sequence[tuple[str, str]]) -> dict[str, Any]:
    return {
        "tag": "div",
        "fields": [
            {
                "is_short": True,
                "text": {"tag": "lark_md", "content": f"**{label}**\n{value}"},
            }
            for label, value in items
        ],
    }


def _markdown_div(content: str) -> dict[str, Any]:
    return {"tag": "div", "text": {"tag": "lark_md", "content": content}}


def _action_bar(buttons: Sequence[tuple[str, str, str]]) -> dict[str, Any]:
    return {
        "tag": "action",
        "actions": [
            {
                "tag": "button",
                "text": {"tag": "plain_text", "content": label},
                "type": btn_type,
                "url": url,
            }
            for label, btn_type, url in buttons
        ],
    }


def _note_block(content: str) -> dict[str, Any]:
    return {"tag": "note", "elements": [{"tag": "plain_text", "content": content}]}


def _build_card(
    *,
    template: str,
    title: str,
    body_elements: Sequence[dict[str, Any]],
    buttons: Sequence[tuple[str, str, str]],
    note: str,
) -> dict[str, Any]:
    elements = [
        *body_elements,
        _action_bar(buttons),
        _note_block(note),
    ]
    return {
        "config": {"wide_screen_mode": True, "enable_forward": True},
        "header": {
            "template": template,
            "title": {"tag": "plain_text", "content": title},
        },
        "elements": elements,
    }


class FeishuCardBuilder:
    """Renders domain models and event payloads into Feishu Interactive Cards."""

    def __init__(
        self,
        *,
        link_builder: NotificationLinkBuilder | None = None,
        config: FeishuCardConfig | None = None,
    ) -> None:
        self.links = link_builder or NotificationLinkBuilder()
        self.config = config or FeishuCardConfig()

    def _fmt_time(self, dt: datetime | str | None) -> str:
        return format_local_time(dt, self.config.timezone_name)

    def violation_alert(self, record: ViolationRecord, *, escalated: bool = False) -> dict[str, Any]:
        vtype_label = VIOLATION_LABELS.get(record.violation_type, record.violation_type)
        severity_label = SEVERITY_DETAILED_LABELS.get(record.severity, record.severity)
        header_template = SEVERITY_TEMPLATES.get(record.severity, "red")
        zone_display = record.zone_name or record.zone_id or "全域监控画面"
        occurred_str = self._fmt_time(record.occurred_at_utc)
        standard_hint = get_standard_hint(record.violation_type, self.config.standard_hint_overrides)
        duration_str = f"{record.duration_seconds:.1f} 秒" if record.duration_seconds > 0 else "实时抓拍"
        short_uuid = record.event_uuid[:8]
        escalation_suffix = "（风险升级）" if escalated else ""

        return _build_card(
            template=header_template,
            title=f"🚨 【施工安全告警{escalation_suffix}】{vtype_label} · {zone_display}",
            body_elements=[
                _fields_div([
                    ("📍 监控点位", f"`{record.camera_id}`"),
                    ("⚠️ 风险等级", severity_label),
                    ("🎯 危险区域", zone_display),
                    ("👤 追踪目标", f"Track `#{record.track_id}` ({duration_str})"),
                    ("🕒 发生时间", occurred_str),
                    ("🔖 事件编号", f"`{short_uuid}`"),
                ]),
                {"tag": "hr"},
                _markdown_div(
                    f"{standard_hint}\n\n💡 **智能体处置建议**：请立即联系点位安全网格员核查现场，并在工作台下发限时整改任务。"
                ),
            ],
            buttons=[
                (
                    "🔧 立即派发整改",
                    "danger" if record.severity == "CRITICAL" else "primary",
                    self.links.route("rectification_tasks", event_uuid=record.event_uuid),
                ),
                (
                    "📸 查看抓拍证据",
                    "default",
                    self.links.route("violations", event_uuid=record.event_uuid),
                ),
                ("🤖 询问安全助手", "default", self.links.route("copilot")),
            ],
            note=f"🛡️ {self.config.brand_name} · 边缘视觉感知实时联动 | 事件 UUID: {record.event_uuid}",
        )

    def rectification_created(self, task: dict[str, Any]) -> dict[str, Any]:
        task_id = str(task.get("task_id", "-"))
        event_uuid = str(task.get("event_uuid", "-"))
        title = str(task.get("title", "安全隐患整改任务"))
        owner = str(task.get("owner", "未指定"))
        due_str = self._fmt_time(task.get("due_at_utc"))
        description = str(
            task.get("description") or "请严格按照国家施工安全技术规范立即完成现场隐患整改并上传复核结果。"
        )

        return _build_card(
            template="blue",
            title=f"📋 【整改督办】已派发安全隐患整改任务：{title}",
            body_elements=[
                _fields_div([
                    ("👷 整改责任人", f"**{owner}**"),
                    ("⏰ 整改截止时间", due_str),
                    ("🔖 任务单号", f"`{task_id[:8]}`"),
                    ("🔗 关联违规事件", f"`{event_uuid[:8]}`"),
                ]),
                {"tag": "hr"},
                _markdown_div(f"**📝 整改要求与说明**：\n{description}"),
            ],
            buttons=[
                ("👉 移动端跟进整改进度", "primary", self.links.route("rectification_tasks")),
                ("📊 打开监控看板", "default", self.links.route("dashboard")),
            ],
            note=f"🛡️ {self.config.brand_name} · 整改闭环督办中心 | 任务 ID: {task_id}",
        )

    def rectification_completed(self, task: dict[str, Any]) -> dict[str, Any]:
        task_id = str(task.get("task_id", "-"))
        event_uuid = str(task.get("event_uuid", "-"))
        title = str(task.get("title", "安全隐患整改"))
        owner = str(task.get("owner", "-"))
        note = str(task.get("note") or "现场复核通过，违规隐患已消除。")
        completed_str = self._fmt_time(task.get("completed_at_utc") or datetime.now(timezone.utc))

        return _build_card(
            template="green",
            title=f"✅ 【隐患销项】整改任务已完成闭环：{title}",
            body_elements=[
                _fields_div([
                    ("👷 完成责任人", owner),
                    ("🕒 闭环销项时间", completed_str),
                    ("🛡️ 关联违规状态", "已解除 (`RESOLVED`)"),
                    ("🔖 关联事件编号", f"`{event_uuid[:8]}`"),
                ]),
                {"tag": "hr"},
                _markdown_div(f"**📋 核销复核记录**：\n{note}"),
            ],
            buttons=[("📋 查看闭环审计台账", "primary", self.links.route("rectification_tasks"))],
            note=f"🛡️ {self.config.brand_name} · 全链路自动销项归档 | 任务 ID: {task_id}",
        )

    def report_confirmed(self, report: ReportResponse) -> dict[str, Any]:
        start_str = self._fmt_time(report.period_start_utc)[:10]
        end_str = self._fmt_time(report.period_end_utc)[:10]
        total_v = report.statistics.get("total", 0)
        repeat_v = report.statistics.get("repeat_occurrences", 0)
        summary_text = _truncate_text(
            report.content.summary,
            "已完成周期安全风险汇总分析。",
            self.config.summary_max_chars,
        )
        remediation_text = _truncate_text(
            report.content.remediation,
            "请各班组严格落实安全技术交底。",
            self.config.remediation_max_chars,
        )
        pdf_link = self.links.resolve_resource_url(report.pdf_url, fallback_route="learning")

        return _build_card(
            template="purple",
            title=f"📊 【安全周报】{start_str} 至 {end_str} 安全风险评估报告已签发",
            body_elements=[
                _fields_div([
                    ("📅 统计周期", f"{start_str} ~ {end_str}"),
                    ("📈 有效违规总数", f"**{total_v}** 起（重复出现 {repeat_v} 次）"),
                ]),
                {"tag": "hr"},
                _markdown_div(
                    f"**🔍 AI 风险综述**：\n{summary_text}\n\n"
                    f"**🛠️ 核心整改建议**：\n{remediation_text}"
                ),
            ],
            buttons=[
                ("📄 预览 / 下载 PDF 正式报告", "primary", pdf_link),
                ("🎓 前往学习中心组织培训", "default", self.links.route("learning")),
            ],
            note=f"🛡️ {self.config.brand_name} · RAG 规范依据核验生成 | 报告 ID: {report.report_id}",
        )

    def training_published(self, training: TrainingResponse) -> dict[str, Any]:
        learn_url = self.links.resolve_resource_url(training.public_url, fallback_route="learning")
        material_preview = _truncate_text(
            (training.material or "").replace("\n", " "),
            "",
            self.config.material_preview_max_chars,
        )

        return _build_card(
            template="turquoise",
            title=f"🎓 【全员安全教育】《{training.title}》线上培训与考核已发布",
            body_elements=[
                _fields_div([
                    ("👥 应参训人数", f"**{training.target_count}** 人"),
                    ("📝 考核标准", f"共 **{training.question_count}** 题 · **{training.pass_score}** 分及格"),
                ]),
                {"tag": "hr"},
                _markdown_div(
                    f"**📖 培训材料核心导读**：\n{material_preview}\n\n"
                    "📲 **参训方式**：请各班组作业人员直接点击下方按钮进入移动端 H5 页面阅读安全材料并完成随堂测试。"
                ),
            ],
            buttons=[
                ("📱 工人端立即进入学习与答题", "primary", learn_url),
                ("📈 查看班组参训率与成绩统计", "default", self.links.route("learning")),
            ],
            note=f"🛡️ {self.config.brand_name} · 靶向安全教育闭环 | 培训任务 ID: {training.task_id}",
        )

    def custom_briefing(self, title: str, summary_markdown: str) -> dict[str, Any]:
        now_str = self._fmt_time(datetime.now(timezone.utc))
        return _build_card(
            template="wathet",
            title=f"🤖 【安全智能体通报】{title}",
            body_elements=[
                _markdown_div(summary_markdown),
                {"tag": "hr"},
            ],
            buttons=[
                ("🖥️ 进入安全监控工作台", "primary", self.links.route("dashboard")),
                ("💬 继续对话安全智能助手", "default", self.links.route("copilot")),
            ],
            note=f"🛡️ {self.config.brand_name} · AI 协同简报 | 推送时间: {now_str}",
        )

    # ---- Backwards-compatible static helpers ----
    @classmethod
    def _compat_instance(
        cls,
        web_base_url: str = DEFAULT_WEB_BASE_URL,
        timezone_name: str = "Asia/Shanghai",
        app_base_path: str = "",
    ) -> "FeishuCardBuilder":
        return cls(
            link_builder=NotificationLinkBuilder(web_base_url, app_base_path=app_base_path),
            config=FeishuCardConfig(timezone_name=timezone_name),
        )

    @classmethod
    def build_violation_alert_card(
        cls,
        record: ViolationRecord,
        web_base_url: str = DEFAULT_WEB_BASE_URL,
        timezone_name: str = "Asia/Shanghai",
        *,
        app_base_path: str = "",
        escalated: bool = False,
    ) -> dict[str, Any]:
        return cls._compat_instance(web_base_url, timezone_name, app_base_path).violation_alert(
            record, escalated=escalated
        )

    @classmethod
    def build_rectification_created_card(
        cls,
        task: dict[str, Any],
        web_base_url: str = DEFAULT_WEB_BASE_URL,
        timezone_name: str = "Asia/Shanghai",
        *,
        app_base_path: str = "",
    ) -> dict[str, Any]:
        return cls._compat_instance(web_base_url, timezone_name, app_base_path).rectification_created(task)

    @classmethod
    def build_rectification_completed_card(
        cls,
        task: dict[str, Any],
        web_base_url: str = DEFAULT_WEB_BASE_URL,
        timezone_name: str = "Asia/Shanghai",
        *,
        app_base_path: str = "",
    ) -> dict[str, Any]:
        return cls._compat_instance(web_base_url, timezone_name, app_base_path).rectification_completed(task)

    @classmethod
    def build_report_confirmed_card(
        cls,
        report: ReportResponse,
        web_base_url: str = DEFAULT_WEB_BASE_URL,
        timezone_name: str = "Asia/Shanghai",
        *,
        app_base_path: str = "",
    ) -> dict[str, Any]:
        return cls._compat_instance(web_base_url, timezone_name, app_base_path).report_confirmed(report)

    @classmethod
    def build_training_published_card(
        cls,
        training: TrainingResponse,
        web_base_url: str = DEFAULT_WEB_BASE_URL,
        timezone_name: str = "Asia/Shanghai",
        *,
        app_base_path: str = "",
    ) -> dict[str, Any]:
        return cls._compat_instance(web_base_url, timezone_name, app_base_path).training_published(training)

    @classmethod
    def build_custom_briefing_card(
        cls,
        title: str,
        summary_markdown: str,
        web_base_url: str = DEFAULT_WEB_BASE_URL,
        timezone_name: str = "Asia/Shanghai",
        *,
        app_base_path: str = "",
    ) -> dict[str, Any]:
        return cls._compat_instance(web_base_url, timezone_name, app_base_path).custom_briefing(
            title, summary_markdown
        )
