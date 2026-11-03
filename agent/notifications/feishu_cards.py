from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

from agent.contracts.learning import ReportResponse, TrainingResponse
from agent.contracts.query import ViolationRecord

VIOLATION_TYPE_LABELS: dict[str, str] = {
    "NO_HELMET": "未佩戴安全帽",
    "DANGER_ZONE_INTRUSION": "危险区域闯入",
    "DWELL_TIMEOUT": "危险区域停留超时",
}

SEVERITY_LABELS: dict[str, str] = {
    "CRITICAL": "严重告警 (CRITICAL)",
    "WARNING": "风险预警 (WARNING)",
    "INFO": "一般提示 (INFO)",
}

SEVERITY_TEMPLATES: dict[str, str] = {
    "CRITICAL": "red",
    "WARNING": "orange",
    "INFO": "blue",
}

STANDARD_CLAUSE_HINTS: dict[str, str] = {
    "NO_HELMET": (
        "📖 **《建筑施工高处作业安全技术规范》JGJ 80-2016 第 3.0.5 条**\n"
        "进入施工现场的人员必须正确佩戴符合国家标准的安全帽，系好下颏带。"
    ),
    "DANGER_ZONE_INTRUSION": (
        "📖 **《建筑机械使用安全技术规程》JGJ 33-2012 第 2.0.15 条**\n"
        "起重吊装及高危机械回转半径禁行区域内，严禁非作业人员擅自进入或穿行。"
    ),
    "DWELL_TIMEOUT": (
        "📖 **《建筑施工安全检查标准》JGJ 59-2011 第 3.1.3 条**\n"
        "高风险受限及临边危险区域严禁人员长时间滞留，须立即组织现场疏导与核查。"
    ),
}


def _format_local_time(dt: datetime | str | None, timezone_name: str = "Asia/Shanghai") -> str:
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


class FeishuCardBuilder:
    """Pure builder converting domain models into Feishu Interactive Cards."""

    @staticmethod
    def build_violation_alert_card(
        record: ViolationRecord,
        web_base_url: str = "http://127.0.0.1:5173",
        timezone_name: str = "Asia/Shanghai",
    ) -> dict[str, Any]:
        base = web_base_url.rstrip("/")
        vtype_label = VIOLATION_TYPE_LABELS.get(record.violation_type, record.violation_type)
        severity_label = SEVERITY_LABELS.get(record.severity, record.severity)
        header_template = SEVERITY_TEMPLATES.get(record.severity, "red")
        zone_display = record.zone_name or record.zone_id or "全域监控画面"
        occurred_str = _format_local_time(record.occurred_at_utc, timezone_name)
        standard_hint = STANDARD_CLAUSE_HINTS.get(
            record.violation_type,
            "📖 **《建筑施工安全检查标准》JGJ 59-2011**\n请现场安全员立即核实现场作业环境并督促整改。",
        )
        duration_str = f"{record.duration_seconds:.1f} 秒" if record.duration_seconds > 0 else "实时抓拍"
        short_uuid = record.event_uuid[:8]

        return {
            "config": {"wide_screen_mode": True, "enable_forward": True},
            "header": {
                "template": header_template,
                "title": {
                    "tag": "plain_text",
                    "content": f"🚨 【施工安全告警】{vtype_label} · {zone_display}",
                },
            },
            "elements": [
                {
                    "tag": "div",
                    "fields": [
                        {
                            "is_short": True,
                            "text": {"tag": "lark_md", "content": f"**📍 监控点位**\n`{record.camera_id}`"},
                        },
                        {
                            "is_short": True,
                            "text": {"tag": "lark_md", "content": f"**⚠️ 风险等级**\n{severity_label}"},
                        },
                        {
                            "is_short": True,
                            "text": {"tag": "lark_md", "content": f"**🎯 危险区域**\n{zone_display}"},
                        },
                        {
                            "is_short": True,
                            "text": {"tag": "lark_md", "content": f"**👤 追踪目标**\nTrack `#{record.track_id}` ({duration_str})"},
                        },
                        {
                            "is_short": True,
                            "text": {"tag": "lark_md", "content": f"**🕒 发生时间**\n{occurred_str}"},
                        },
                        {
                            "is_short": True,
                            "text": {"tag": "lark_md", "content": f"**🔖 事件编号**\n`{short_uuid}`"},
                        },
                    ],
                },
                {"tag": "hr"},
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"{standard_hint}\n\n💡 **智能体处置建议**：请立即联系点位安全网格员核查现场，并在工作台下发限时整改任务。",
                    },
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "🔧 立即派发整改"},
                            "type": "primary" if record.severity != "CRITICAL" else "danger",
                            "url": f"{base}/rectification-tasks?event_uuid={record.event_uuid}",
                        },
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "📸 查看抓拍证据"},
                            "type": "default",
                            "url": f"{base}/violations?event_uuid={record.event_uuid}",
                        },
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "🤖 询问安全助手"},
                            "type": "default",
                            "url": f"{base}/copilot",
                        },
                    ],
                },
                {
                    "tag": "note",
                    "elements": [
                        {
                            "tag": "plain_text",
                            "content": f"🛡️ 智慧施工安全智能体 · 边缘视觉感知实时联动 | 事件 UUID: {record.event_uuid}",
                        }
                    ],
                },
            ],
        }

    @staticmethod
    def build_rectification_created_card(
        task: dict[str, Any],
        web_base_url: str = "http://127.0.0.1:5173",
        timezone_name: str = "Asia/Shanghai",
    ) -> dict[str, Any]:
        base = web_base_url.rstrip("/")
        task_id = str(task.get("task_id", "-"))
        event_uuid = str(task.get("event_uuid", "-"))
        title = str(task.get("title", "安全隐患整改任务"))
        owner = str(task.get("owner", "未指定"))
        due_str = _format_local_time(task.get("due_at_utc"), timezone_name)
        description = str(task.get("description") or "请严格按照国家施工安全技术规范立即完成现场隐患整改并上传复核结果。")

        return {
            "config": {"wide_screen_mode": True, "enable_forward": True},
            "header": {
                "template": "blue",
                "title": {
                    "tag": "plain_text",
                    "content": f"📋 【整改督办】已派发安全隐患整改任务：{title}",
                },
            },
            "elements": [
                {
                    "tag": "div",
                    "fields": [
                        {
                            "is_short": True,
                            "text": {"tag": "lark_md", "content": f"**👷 整改责任人**\n**{owner}**"},
                        },
                        {
                            "is_short": True,
                            "text": {"tag": "lark_md", "content": f"**⏰ 整改截止时间**\n{due_str}"},
                        },
                        {
                            "is_short": True,
                            "text": {"tag": "lark_md", "content": f"**🔖 任务单号**\n`{task_id[:8]}`"},
                        },
                        {
                            "is_short": True,
                            "text": {"tag": "lark_md", "content": f"**🔗 关联违规事件**\n`{event_uuid[:8]}`"},
                        },
                    ],
                },
                {"tag": "hr"},
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**📝 整改要求与说明**：\n{description}",
                    },
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "👉 移动端跟进整改进度"},
                            "type": "primary",
                            "url": f"{base}/rectification-tasks",
                        },
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "📊 打开监控看板"},
                            "type": "default",
                            "url": f"{base}/dashboard",
                        },
                    ],
                },
                {
                    "tag": "note",
                    "elements": [
                        {
                            "tag": "plain_text",
                            "content": f"🛡️ 智慧施工安全智能体 · 整改闭环督办中心 | 任务 ID: {task_id}",
                        }
                    ],
                },
            ],
        }

    @staticmethod
    def build_rectification_completed_card(
        task: dict[str, Any],
        web_base_url: str = "http://127.0.0.1:5173",
        timezone_name: str = "Asia/Shanghai",
    ) -> dict[str, Any]:
        base = web_base_url.rstrip("/")
        task_id = str(task.get("task_id", "-"))
        event_uuid = str(task.get("event_uuid", "-"))
        title = str(task.get("title", "安全隐患整改"))
        owner = str(task.get("owner", "-"))
        note = str(task.get("note") or "现场复核通过，违规隐患已消除。")
        completed_str = _format_local_time(task.get("completed_at_utc") or datetime.now(timezone.utc), timezone_name)

        return {
            "config": {"wide_screen_mode": True, "enable_forward": True},
            "header": {
                "template": "green",
                "title": {
                    "tag": "plain_text",
                    "content": f"✅ 【隐患销项】整改任务已完成闭环：{title}",
                },
            },
            "elements": [
                {
                    "tag": "div",
                    "fields": [
                        {
                            "is_short": True,
                            "text": {"tag": "lark_md", "content": f"**👷 完成责任人**\n{owner}"},
                        },
                        {
                            "is_short": True,
                            "text": {"tag": "lark_md", "content": f"**🕒 闭环销项时间**\n{completed_str}"},
                        },
                        {
                            "is_short": True,
                            "text": {"tag": "lark_md", "content": f"**🛡️ 关联违规状态**\n已解除 (`RESOLVED`)"},
                        },
                        {
                            "is_short": True,
                            "text": {"tag": "lark_md", "content": f"**🔖 关联事件编号**\n`{event_uuid[:8]}`"},
                        },
                    ],
                },
                {"tag": "hr"},
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": f"**📋 核销复核记录**：\n{note}",
                    },
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "📋 查看闭环审计台账"},
                            "type": "primary",
                            "url": f"{base}/rectification-tasks",
                        }
                    ],
                },
                {
                    "tag": "note",
                    "elements": [
                        {
                            "tag": "plain_text",
                            "content": f"🛡️ 智慧施工安全智能体 · 全链路自动销项归档 | 任务 ID: {task_id}",
                        }
                    ],
                },
            ],
        }

    @staticmethod
    def build_report_confirmed_card(
        report: ReportResponse,
        web_base_url: str = "http://127.0.0.1:5173",
        timezone_name: str = "Asia/Shanghai",
    ) -> dict[str, Any]:
        base = web_base_url.rstrip("/")
        start_str = _format_local_time(report.period_start_utc, timezone_name)[:10]
        end_str = _format_local_time(report.period_end_utc, timezone_name)[:10]
        total_v = report.statistics.get("total", 0)
        repeat_v = report.statistics.get("repeat_occurrences", 0)
        summary_text = (report.content.summary or "已完成周期安全风险汇总分析。").strip()
        if len(summary_text) > 200:
            summary_text = summary_text[:200] + "..."
        remediation_text = (report.content.remediation or "请各班组严格落实安全技术交底。").strip()
        if len(remediation_text) > 160:
            remediation_text = remediation_text[:160] + "..."

        pdf_link = f"{base}{report.pdf_url}" if report.pdf_url and report.pdf_url.startswith("/") else (report.pdf_url or f"{base}/learning")

        return {
            "config": {"wide_screen_mode": True, "enable_forward": True},
            "header": {
                "template": "purple",
                "title": {
                    "tag": "plain_text",
                    "content": f"📊 【安全周报】{start_str} 至 {end_str} 安全风险评估报告已签发",
                },
            },
            "elements": [
                {
                    "tag": "div",
                    "fields": [
                        {
                            "is_short": True,
                            "text": {"tag": "lark_md", "content": f"**📅 统计周期**\n{start_str} ~ {end_str}"},
                        },
                        {
                            "is_short": True,
                            "text": {"tag": "lark_md", "content": f"**📈 有效违规总数**\n**{total_v}** 起（重复出现 {repeat_v} 次）"},
                        },
                    ],
                },
                {"tag": "hr"},
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": (
                            f"**🔍 AI 风险综述**：\n{summary_text}\n\n"
                            f"**🛠️ 核心整改建议**：\n{remediation_text}"
                        ),
                    },
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "📄 预览 / 下载 PDF 正式报告"},
                            "type": "primary",
                            "url": pdf_link,
                        },
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "🎓 前往学习中心组织培训"},
                            "type": "default",
                            "url": f"{base}/learning",
                        },
                    ],
                },
                {
                    "tag": "note",
                    "elements": [
                        {
                            "tag": "plain_text",
                            "content": f"🛡️ 智慧施工安全智能体 · RAG 规范依据核验生成 | 报告 ID: {report.report_id}",
                        }
                    ],
                },
            ],
        }

    @staticmethod
    def build_training_published_card(
        training: TrainingResponse,
        web_base_url: str = "http://127.0.0.1:5173",
        timezone_name: str = "Asia/Shanghai",
    ) -> dict[str, Any]:
        base = web_base_url.rstrip("/")
        learn_url = training.public_url or f"{base}/learning"
        material_preview = (training.material or "").strip().replace("\n", " ")
        if len(material_preview) > 150:
            material_preview = material_preview[:150] + "..."

        return {
            "config": {"wide_screen_mode": True, "enable_forward": True},
            "header": {
                "template": "turquoise",
                "title": {
                    "tag": "plain_text",
                    "content": f"🎓 【全员安全教育】《{training.title}》线上培训与考核已发布",
                },
            },
            "elements": [
                {
                    "tag": "div",
                    "fields": [
                        {
                            "is_short": True,
                            "text": {"tag": "lark_md", "content": f"**👥 应参训人数**\n**{training.target_count}** 人"},
                        },
                        {
                            "is_short": True,
                            "text": {"tag": "lark_md", "content": f"**📝 考核标准**\n共 **{training.question_count}** 题 · **{training.pass_score}** 分及格"},
                        },
                    ],
                },
                {"tag": "hr"},
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": (
                            f"**📖 培训材料核心导读**：\n{material_preview}\n\n"
                            "📲 **参训方式**：请各班组作业人员直接点击下方按钮进入移动端 H5 页面阅读安全材料并完成随堂测试。"
                        ),
                    },
                },
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "📱 工人端立即进入学习与答题"},
                            "type": "primary",
                            "url": learn_url,
                        },
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "📈 查看班组参训率与成绩统计"},
                            "type": "default",
                            "url": f"{base}/learning",
                        },
                    ],
                },
                {
                    "tag": "note",
                    "elements": [
                        {
                            "tag": "plain_text",
                            "content": f"🛡️ 智慧施工安全智能体 · 靶向安全教育闭环 | 培训任务 ID: {training.task_id}",
                        }
                    ],
                },
            ],
        }

    @staticmethod
    def build_custom_briefing_card(
        title: str,
        summary_markdown: str,
        web_base_url: str = "http://127.0.0.1:5173",
        timezone_name: str = "Asia/Shanghai",
    ) -> dict[str, Any]:
        base = web_base_url.rstrip("/")
        now_str = _format_local_time(datetime.now(timezone.utc), timezone_name)

        return {
            "config": {"wide_screen_mode": True, "enable_forward": True},
            "header": {
                "template": "wathet",
                "title": {
                    "tag": "plain_text",
                    "content": f"🤖 【安全智能体通报】{title}",
                },
            },
            "elements": [
                {
                    "tag": "div",
                    "text": {
                        "tag": "lark_md",
                        "content": summary_markdown,
                    },
                },
                {"tag": "hr"},
                {
                    "tag": "action",
                    "actions": [
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "🖥️ 进入安全监控工作台"},
                            "type": "primary",
                            "url": f"{base}/dashboard",
                        },
                        {
                            "tag": "button",
                            "text": {"tag": "plain_text", "content": "💬 继续对话安全智能助手"},
                            "type": "default",
                            "url": f"{base}/copilot",
                        },
                    ],
                },
                {
                    "tag": "note",
                    "elements": [
                        {
                            "tag": "plain_text",
                            "content": f"🛡️ 智慧施工安全智能体 · AI 协同简报 | 推送时间: {now_str}",
                        }
                    ],
                },
            ],
        }
