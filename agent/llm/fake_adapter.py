from __future__ import annotations

import re
from datetime import datetime, timezone
from collections.abc import Sequence
from typing import Any

from agent.contracts.chat import ToolDecision, ToolResult
from agent.contracts.query import ViolationQuery
from agent.tools.weather import extract_weather_location
from .protocol import ChatModelPort


class FakeChatModel(ChatModelPort):
    """Deterministic adapter for local development and graph/API tests."""

    model_name = "fake-safety-chat-v1"

    def decide(self, question: str, previous_results: Sequence[ToolResult], memory_context: str = "", tool_catalog: Sequence[dict[str, str]] = ()) -> ToolDecision | None:
        normalized = question.lower()
        camera_id = self._camera_id(question)
        if previous_results:
            if self._asks_for_latest(normalized) and previous_results[-1].tool_name == "get_violation_statistics":
                return ToolDecision(
                    tool_name="query_violations",
                    query=self._query(camera_id, normalized),
                    purpose="补充最近的违规事件作为统计依据",
                )
            return None
        if any(token in question for token in ("启动监控", "开启监控", "开始监控")):
            return ToolDecision(tool_name="start_monitoring", camera_id=camera_id, purpose="生成摄像头监控启动的待确认操作") if camera_id else None
        if any(token in question for token in ("停止监控", "关闭监控", "结束监控")):
            return ToolDecision(tool_name="stop_monitoring", camera_id=camera_id, purpose="生成摄像头监控停止的待确认操作") if camera_id else None
        if any(token in question for token in ("创建整改", "新建整改", "派发整改")):
            event_uuid = self._uuid(question)
            due_at = self._due_at(question)
            owner = self._owner(question)
            title = self._task_title(question)
            if event_uuid and due_at and owner and title:
                return ToolDecision(
                    tool_name="create_rectification_task", violation_event_uuid=event_uuid, task_title=title,
                    task_owner=owner, task_due_at_utc=due_at, purpose="生成违规整改任务的待确认操作",
                )
            return None
        if any(token in question for token in ("完成整改任务", "更新整改任务", "修改整改任务")):
            task_id = self._uuid(question)
            if not task_id:
                return None
            status = "COMPLETED" if "完成" in question else None
            owner = self._owner(question)
            note_match = re.search(r"备注[：:]?([^，。；;]+)", question)
            if not any((status, owner, note_match)):
                return None
            return ToolDecision(
                tool_name="update_rectification_task", task_id=task_id, task_status=status,
                task_owner=owner, task_note=note_match.group(1).strip() if note_match else None,
                purpose="生成整改任务更新的待确认操作",
            )
        if any(token in normalized for token in ("天气", "气温", "温度", "降雨", "下雨", "风速")):
            location = extract_weather_location(question)
            if location:
                return ToolDecision(
                    tool_name="get_current_weather",
                    weather_location=location,
                    purpose=f"查询 {location} 的当前天气",
                )
            return None
        if (any(token in question for token in ("所有摄像头", "全部摄像头", "全体摄像头", "所有相机", "全部相机")) and any(token in normalized for token in ("状态", "在线", "运行", "fps", "帧率"))) or any(token in question for token in ("工人", "人员", "人数", "在场人数", "多少人")):
            return ToolDecision(tool_name="get_all_camera_statuses", purpose="查询全部摄像头的综合运行状态与帧率")
        if "状态" in question or "在线" in question or "fps" in normalized:
            return ToolDecision(tool_name="get_camera_status", camera_id=camera_id or "A01", purpose="查询摄像头最新运行状态")
        if self._asks_for_statistics(normalized):
            return ToolDecision(tool_name="get_violation_statistics", query=self._query(camera_id, normalized), purpose="汇总违规数量和严重级别")
        return ToolDecision(tool_name="query_violations", query=self._query(camera_id, normalized), purpose="查询符合条件的违规事件")

    def respond(self, question: str, results: Sequence[ToolResult], memory_context: str = "") -> str:
        if not results:
            return "未找到可用于回答的安全数据。"
        fragments: list[str] = []
        for result in results:
            if result.tool_name == "get_violation_statistics":
                payload = result.data if isinstance(result.data, dict) else {}
                fragments.append(f"查询范围内共有 {payload.get('total_violations', 0)} 条违规，其中严重违规 {payload.get('by_severity', {}).get('CRITICAL', 0)} 条。")
            elif result.tool_name == "query_violations":
                rows = result.data if isinstance(result.data, list) else []
                if rows:
                    latest = rows[0]
                    fragments.append(f"最近一条为 {latest.get('violation_type', '违规')}，发生于 {latest.get('occurred_at_utc', '未知时间')}。")
                else:
                    fragments.append("未查询到符合条件的违规事件。")
            elif result.tool_name == "get_camera_status":
                payload = result.data if isinstance(result.data, dict) else None
                if payload:
                    fragments.append(f"摄像头 {payload.get('camera_id')} 当前{'在线' if payload.get('is_online') else '离线'}，FPS 为 {payload.get('fps')}。")
                else:
                    fragments.append("未找到该摄像头的状态上报。")
            elif result.tool_name == "get_all_camera_statuses":
                rows = result.data if isinstance(result.data, list) else []
                if not rows:
                    fragments.append("当前未查询到摄像头状态上报。")
                else:
                    details = "；".join(
                        f"{row.get('camera_id')} {'在线' if row.get('is_online') else '离线'}，FPS {row.get('fps')}"
                        for row in rows if isinstance(row, dict)
                    )
                    online_workers = sum(int(row.get("active_workers_count") or 0) for row in rows if isinstance(row, dict) and row.get("is_online"))
                    fragments.append(f"当前共 {len(rows)} 路摄像头：{details}。在线摄像头上报的活跃作业人数合计为 {online_workers}。")
            elif result.tool_name == "get_current_weather":
                payload = result.data if isinstance(result.data, dict) else {}
                if payload:
                    fragments.append(
                        f"{payload.get('location', '该地点')}当前{payload.get('weather_summary', '天气未知')}，"
                        f"气温 {payload.get('temperature_c', '未知')}°C，"
                        f"风速 {payload.get('wind_speed_kmh', '未知')} km/h。"
                    )
                else:
                    fragments.append("未查询到该地点的天气信息。")
        return "".join(fragments)

    def generate_structured(self, instruction: str, context: dict[str, Any]) -> dict[str, Any]:
        if "文档摘要" in instruction:
            excerpts = context.get("excerpts") or []
            text = " ".join(str(item.get("text", "")) for item in excerpts if isinstance(item, dict))
            return {"summary": (text[:150].strip() or f"{context.get('title', '该文档')}：原文片段未提供可概括内容。")}
        if "题目" in instruction:
            count = int(context.get("question_count", 5))
            report = context.get("report") or {}
            source_texts = [str(report.get(key, "")) for key in ("risk_analysis", "remediation", "summary")]
            source_texts.extend(str(chunk.get("content", "")) for doc in context.get("documents", []) for chunk in doc.get("chunks", []))
            evidence = []
            for source in source_texts:
                for sentence in re.split(r"[。！？\n]", source):
                    sentence = sentence.strip()
                    if sentence and sentence not in evidence:
                        evidence.append(sentence)
            questions = []
            for sentence in evidence[:count]:
                questions.append({"stem": f"关于“{sentence[:18]}”所述的现场安全要求，哪项与学习资料一致？",
                                  "options": [sentence, "风险出现后可继续冒险作业", "只口头提醒，无需落实整改", "忽略隐患，等待下次培训再处理"],
                                  "answer": 0, "evidence": sentence})
            return {"material": "请阅读本期安全报告与所选资料，重点学习现场风险识别、隐患处置与防范措施。", "questions": questions}
        if "事故经过" in instruction:
            return {"process": "依据已收录文档片段查看事故经过。", "causes": "请核对原文。", "risks": "请核对原文。", "prevention": "按现场管理要求防范。"}
        return {"summary": "根据统计数据形成的安全报告草稿。", "risk_analysis": "请结合统计表核对风险分布。", "remediation": "针对高频违规开展现场整改。"}

    @staticmethod
    def _camera_id(question: str) -> str | None:
        # Camera IDs are deployment-defined and commonly contain multiple
        # hyphen/underscore-delimited segments (for example ``cam_e2e_01``).
        # Match the complete identifier instead of a trailing partial segment.
        match = re.search(r"(?:摄像头\s*)?([A-Za-z][A-Za-z0-9]*(?:[-_][A-Za-z0-9]+)*)\b", question)
        return match.group(1) if match else None

    @staticmethod
    def _asks_for_statistics(normalized: str) -> bool:
        return any(token in normalized for token in ("多少", "几条", "统计", "数量", "count", "total"))

    @staticmethod
    def _asks_for_latest(normalized: str) -> bool:
        return any(token in normalized for token in ("最近", "最新", "last", "latest"))

    @staticmethod
    def _uuid(question: str) -> str | None:
        match = re.search(r"\b[0-9a-fA-F]{8}-(?:[0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12}\b", question)
        return match.group(0) if match else None

    @staticmethod
    def _due_at(question: str) -> datetime | None:
        match = re.search(r"\b(20\d{2}-\d{2}-\d{2}(?:[T\s]\d{2}:\d{2}(?::\d{2})?(?:Z|[+-]\d{2}:?\d{2})?)?)\b", question)
        if not match:
            return None
        value = match.group(1).replace(" ", "T")
        if len(value) == 10:
            value += "T18:00:00+00:00"
        elif value.endswith("Z"):
            value = value[:-1] + "+00:00"
        parsed = datetime.fromisoformat(value)
        return parsed.replace(tzinfo=timezone.utc) if parsed.tzinfo is None else parsed

    @staticmethod
    def _owner(question: str) -> str | None:
        match = re.search(r"负责人(?:为|是|：|:)?\s*([^，。；;\s]{2,32})", question)
        return match.group(1).strip() if match else None

    @staticmethod
    def _task_title(question: str) -> str | None:
        match = re.search(r"(?:创建|新建|派发)整改(?:任务)?[：:]?\s*([^，。；;]{2,120})", question)
        return match.group(1).strip() if match else None

    @staticmethod
    def _query(camera_id: str | None, normalized: str) -> ViolationQuery:
        severity = "CRITICAL" if ("严重" in normalized or "critical" in normalized) else None
        return ViolationQuery(camera_id=camera_id, severity=severity, limit=20)
