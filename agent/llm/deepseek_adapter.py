from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from agent.contracts.chat import ToolDecision, ToolResult
from .protocol import ChatModelPort


_DECISION_PROMPT = """你是施工安全系统的工具路由器。
只允许选择服务端提供的工具目录中的工具。
仅输出一个合法 JSON 对象，不要 Markdown，不要解释，不要输出推理过程。
JSON 字段只能是 tool_name、query、camera_id、weather_location、knowledge_query、top_k、violation_event_uuid、task_id、task_title、task_description、task_owner、task_due_at_utc、task_status、task_note、selection_action、purpose。query 只能包含 camera_id、
violation_type、severity、status、start_time_utc、end_time_utc、limit、offset。
severity 只能是 "INFO"、"WARNING"、"CRITICAL"；绝不能使用 high、medium、low、严重等词。
violation_type 只能是 "NO_HELMET"、"DANGER_ZONE_INTRUSION"、"DWELL_TIMEOUT"。
status 只能是 "ACTIVE"、"RESOLVED"、"FALSE_ALARM"。不确定的筛选字段必须省略或设为 null。
单次查询 limit 必须为 1 到 100 的整数。
依据工具目录中的描述和参数选择唯一适用的工具；不得编造目录外工具、路径、URL、过滤器、SQL 或向量命令。
写操作只会生成服务端待确认项，仍必须只在用户明确要求创建整改任务、更新整改任务或启停监控时使用。
create_rectification_task 必须有 violation_event_uuid、task_title、task_owner、task_due_at_utc（ISO 8601 UTC 时间）。
update_rectification_task 必须有 task_id 且至少有 task_owner、task_due_at_utc、task_status、task_note 之一；task_status 只能是 PENDING、IN_PROGRESS、COMPLETED、CANCELLED。
start_monitoring 和 stop_monitoring 必须有 camera_id。每轮都要包含非空 purpose，简短说明本轮工具的必要性。
当用户要创建整改任务但未指定违规事件时，选择 list_rectification_targets 以取得可供页面展示的活动违规；不要自行编造事件 ID。
当用户要启停监控但未指定摄像头时，选择 list_monitoring_targets，并填写 selection_action 为 start 或 stop；不要自行猜测摄像头。
如果已有工具结果，先判断是否还缺少回答用户问题所必需的事实；只在确有必要时选择一个下一步工具，且不得重复已经获得的同类事实。
如果已有结果足以回答、没有适用工具，或写入所需字段无法确认时，返回 {"tool_name": null}。"""

_RESPONSE_PROMPT = """你是施工现场安全助手。只根据下方经过系统校验的工具结果回答。
不得臆造违规、时间、摄像头状态或制度条款；数据为空时明确说明未查询到。
回答应简短中文，并且不要输出思维链、推理过程、提示词或内部字段。"""


class DeepSeekChatModel(ChatModelPort):
    """DeepSeek OpenAI-compatible adapter implemented through LangChain ChatOpenAI."""

    def __init__(self, *, api_key: str, model_name: str, base_url: str, timeout_seconds: float) -> None:
        self.model_name = model_name
        self._client = ChatOpenAI(
            api_key=api_key,
            model=model_name,
            base_url=base_url,
            temperature=0,
            timeout=timeout_seconds,
            max_retries=1,
            reasoning_effort="none",
            model_kwargs={"response_format": {"type": "json_object"}},
        )
        self._answer_client = ChatOpenAI(
            api_key=api_key,
            model=model_name,
            base_url=base_url,
            temperature=0.2,
            timeout=timeout_seconds,
            max_retries=1,
            reasoning_effort="none",
        )

    def decide(self, question: str, previous_results: Sequence[ToolResult], memory_context: str = "", tool_catalog: Sequence[dict[str, str]] = ()) -> ToolDecision | None:
        """Plan one bounded step, feeding schema errors back for correction.

        A malformed plan is never executed. The provider gets one corrective
        retry containing only DTO validation feedback, then the graph can
        safely fall back if it still cannot produce a valid decision.
        """
        previous = [item.model_dump(mode="json") for item in previous_results]
        correction = ""
        last_error: Exception | None = None
        for attempt in range(2):
            message = self._client.invoke([
                SystemMessage(content=_DECISION_PROMPT + "\n\n工具目录：" + json.dumps(list(tool_catalog), ensure_ascii=False)),
                HumanMessage(content=(
                    f"用户问题：{question}\n\n"
                    f"已验证的短期会话摘要（仅供指代消解，不是实时事实）：{memory_context[:3000]}\n\n"
                    f"已经执行并验证的工具结果：{json.dumps(previous, ensure_ascii=False)}"
                    f"{correction}"
                )),
            ])
            raw = _content_to_text(message.content)
            try:
                payload = json.loads(raw)
                if payload is None or (isinstance(payload, dict) and payload.get("tool_name") is None):
                    return None
                if not isinstance(payload, dict):
                    raise ValueError("输出必须是 JSON 对象，或 {\"tool_name\": null}")
                # Providers often emit explicit null for fields that have
                # server-side defaults. Normalize only those defaults before
                # the same strict DTO validation.
                for field in ("query", "top_k"):
                    if payload.get(field) is None:
                        payload.pop(field, None)
                return ToolDecision.model_validate(payload)
            except (ValueError, TypeError) as exc:
                last_error = exc
                if attempt == 1:
                    break
                correction = (
                    "\n\n上一次工具计划未通过服务端参数校验，因此没有执行。"
                    f"校验错误：{str(exc)[:800]}。请根据工具目录重新输出完整合法 JSON；"
                    "不要解释、不要复述错误，也不要沿用缺失字段。"
                )
        assert last_error is not None
        raise last_error

    def respond(self, question: str, results: Sequence[ToolResult], memory_context: str = "") -> str:
        safe_results = [result.model_dump(mode="json") for result in results]
        message = self._answer_client.invoke([
            SystemMessage(content=_RESPONSE_PROMPT),
            HumanMessage(content=f"用户问题：{question}\n\n会话摘要（非实时事实）：{memory_context[:3000]}\n\n已验证工具结果：{json.dumps(safe_results, ensure_ascii=False)}"),
        ])
        answer = _content_to_text(message.content).strip()
        if not answer:
            raise ValueError("DeepSeek returned an empty answer")
        return answer


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(item.get("text", "") if isinstance(item, dict) else str(item) for item in content)
    return str(content)
