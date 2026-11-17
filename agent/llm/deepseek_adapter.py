from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any

from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI

from agent.contracts.chat import ToolDecision, ToolResult
from agent.prompts import load_prompt, render_decision_prompt
from .protocol import ChatModelPort


_DECISION_PROMPT = render_decision_prompt()
_RESPONSE_PROMPT = load_prompt("response")
_STRUCTURED_SYSTEM_PROMPT = load_prompt("structured_system")


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

    def respond(
        self,
        question: str,
        results: Sequence[ToolResult],
        memory_context: str = "",
        tool_catalog: Sequence[dict[str, str]] = (),
        capability_status: dict[str, Any] | None = None,
        response_locale: str = "zh-CN",
    ) -> str:
        safe_results = [result.model_dump(mode="json") for result in results]
        capability_section = ""
        if tool_catalog or capability_status:
            status_payload = capability_status or {}
            capability_payload = {
                "available_tools": list(tool_catalog),
                "capabilities": status_payload.get("capabilities", []),
                "disabled_tools": status_payload.get("disabled_tools", []),
                "active_notification_channels": status_payload.get("active_notification_channels", []),
            }
            capability_section = (
                "\n\n当前系统可用工具目录与能力状态（仅供如实说明已启用/未启用能力；未执行的工具不代表已执行）："
                + json.dumps(capability_payload, ensure_ascii=False)
            )
        system_prompt = _RESPONSE_PROMPT + _locale_response_instruction(response_locale)
        message = self._answer_client.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(
                content=(
                    f"用户问题：{question}\n\n"
                    f"会话摘要（非实时事实）：{memory_context[:3000]}"
                    f"{capability_section}\n\n"
                    f"已验证工具结果：{json.dumps(safe_results, ensure_ascii=False)}"
                )
            ),
        ])
        answer = _content_to_text(message.content).strip()
        if not answer:
            raise ValueError("DeepSeek returned an empty answer")
        return answer

    def generate_structured(
        self,
        instruction: str,
        context: dict[str, Any],
        response_locale: str = "zh-CN",
    ) -> dict[str, Any]:
        system_prompt = _STRUCTURED_SYSTEM_PROMPT + instruction + _locale_structured_instruction(response_locale)
        message = self._client.invoke([
            SystemMessage(content=system_prompt),
            HumanMessage(content=json.dumps(context, ensure_ascii=False, default=str)),
        ])
        payload = json.loads(_content_to_text(message.content))
        if not isinstance(payload, dict):
            raise ValueError("model must return a JSON object")
        return payload


def _locale_response_instruction(response_locale: str) -> str:
    if response_locale == "zh-HK":
        return "\n输出语言要求：请严格使用规范繁体中文（Traditional Chinese）作答，保持原有工程专业术语与标点习惯，不要夹杂简体字。"
    return ""


def _locale_structured_instruction(response_locale: str) -> str:
    if response_locale == "zh-HK":
        return "\n输出语言要求：面向用户展示的 JSON 文本字段请使用规范繁体中文，JSON 键名和枚举代码保持不变。"
    return ""


def _content_to_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        return "".join(item.get("text", "") if isinstance(item, dict) else str(item) for item in content)
    return str(content)
