from __future__ import annotations

import re
from collections.abc import Sequence
from typing import Any

from agent.contracts.chat import ToolDecision, ToolResult
from agent.contracts.query import ViolationQuery
from .protocol import ChatModelPort


class FakeChatModel(ChatModelPort):
    """Deterministic adapter for local development and graph/API tests."""

    model_name = "fake-safety-chat-v1"

    def decide(self, question: str, previous_results: Sequence[ToolResult]) -> ToolDecision | None:
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
        if "状态" in question or "在线" in question or "fps" in normalized:
            return ToolDecision(tool_name="get_camera_status", camera_id=camera_id or "A01", purpose="查询摄像头最新运行状态")
        if self._asks_for_statistics(normalized):
            return ToolDecision(tool_name="get_violation_statistics", query=self._query(camera_id, normalized), purpose="汇总违规数量和严重级别")
        return ToolDecision(tool_name="query_violations", query=self._query(camera_id, normalized), purpose="查询符合条件的违规事件")

    def respond(self, question: str, results: Sequence[ToolResult]) -> str:
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
        return "".join(fragments)

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
    def _query(camera_id: str | None, normalized: str) -> ViolationQuery:
        severity = "CRITICAL" if ("严重" in normalized or "critical" in normalized) else None
        return ViolationQuery(camera_id=camera_id, severity=severity, limit=20)
