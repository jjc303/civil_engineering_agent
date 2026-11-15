from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from fastapi.testclient import TestClient

from agent.contracts.chat import ChatRequest, ToolDecision, ToolResult
from agent.core.config import Settings
from agent.db.base import Database
from agent.main import create_app
from agent.notifications import BaseNotificationChannel, CompositeNotificationService
from agent.repositories.violations import ViolationRepository
from agent.services.chat_service import ChatService
from agent.tools.base import AgentTool, ToolContext, ToolOutcome
from agent.tools.catalog import DEFAULT_TOOL_CATALOG


class _CustomWeComChannel(BaseNotificationChannel):
    channel_name = "wecom"
    channel_label = "企业微信安全群"
    channel_aliases = ("wecom", "企微", "企业微信")

    def __init__(self) -> None:
        self.sent: list[tuple[str, str]] = []

    def send_custom_briefing(
        self,
        title: str,
        summary_markdown: str,
        *,
        sync: bool = False,
    ) -> dict[str, Any]:
        self.sent.append((title, summary_markdown))
        return {"ok": True, "channel": self.channel_name}


class _InspectingChatModel:
    model_name = "inspecting-model"

    def __init__(self) -> None:
        self.respond_calls: list[dict[str, Any]] = []

    def decide(
        self,
        question: str,
        previous_results: Sequence[ToolResult],
        memory_context: str = "",
        tool_catalog: Sequence[dict[str, str]] = (),
    ) -> ToolDecision | None:
        return None

    def respond(
        self,
        question: str,
        results: Sequence[ToolResult],
        memory_context: str = "",
        tool_catalog: Sequence[dict[str, str]] = (),
        capability_status: dict[str, Any] | None = None,
    ) -> str:
        self.respond_calls.append({
            "question": question,
            "results": list(results),
            "memory_context": memory_context,
            "tool_catalog": list(tool_catalog),
            "capability_status": capability_status,
        })
        return "ok"

    def generate_structured(self, instruction: str, context: dict[str, Any]) -> dict[str, Any]:
        return {}


class _LegacyThreeArgModel:
    model_name = "legacy-3-arg"

    def decide(
        self,
        question: str,
        previous_results: Sequence[ToolResult],
        memory_context: str = "",
        tool_catalog: Sequence[dict[str, str]] = (),
    ) -> ToolDecision | None:
        return None

    def respond(
        self,
        question: str,
        results: Sequence[ToolResult],
        memory_context: str = "",
    ) -> str:
        return "legacy-ok"

    def generate_structured(self, instruction: str, context: dict[str, Any]) -> dict[str, Any]:
        return {}


def test_intent_pruning_uses_tool_metadata_and_channel_aliases() -> None:
    wecom = _CustomWeComChannel()
    ctx = ToolContext(repository=ViolationRepository(None), notification_service=wecom)  # type: ignore[arg-type]

    custom_tool = AgentTool(
        name="custom_drone_patrol",
        description="触发无人机现场巡查",
        parameters="drone_id: string",
        handler=lambda dec, c: ToolOutcome(data={"patrol": "started"}),
        intent_keywords=("无人机", "巡查"),
    )
    extended = DEFAULT_TOOL_CATALOG.with_tools(custom_tool)

    drone_tools = extended.available_catalog(ctx, question="请派无人机巡查东门区域", prune_by_intent=True)
    assert any(t["name"] == "custom_drone_patrol" for t in drone_tools)

    wecom_tools = extended.available_catalog(ctx, question="请通过企微群发一条安全通报", prune_by_intent=True)
    assert any(t["name"] == "send_feishu_notification" for t in wecom_tools)
    assert not any(t["name"] == "get_current_weather" for t in wecom_tools)


def test_notification_tool_adapts_description_and_answer_to_active_channel() -> None:
    wecom = _CustomWeComChannel()
    db = Database("sqlite+pysqlite:///:memory:")
    db.create_schema()

    with db.session() as session:
        ctx = ToolContext(repository=ViolationRepository(session), notification_service=wecom)
        catalog_entries = DEFAULT_TOOL_CATALOG.available_catalog(ctx)
        notify_entry = next(item for item in catalog_entries if item["name"] == "send_feishu_notification")
        assert "企业微信安全群" in notify_entry["description"]
        assert "飞书" not in notify_entry["description"]

        outcome = DEFAULT_TOOL_CATALOG.get("send_feishu_notification").execute(
            ToolDecision(tool_name="send_feishu_notification", notification_title="今日隐患播报", purpose="p"),
            ctx,
        )
        assert outcome.success is True
        assert outcome.answer is not None
        assert "企业微信安全群" in outcome.answer
        assert "飞书" not in outcome.answer
        assert len(wecom.sent) == 1

    composite = CompositeNotificationService([wecom])
    assert composite.active_channel_labels() == ["企业微信安全群"]


def test_chat_service_passes_catalog_and_capability_status_to_respond_safely() -> None:
    db = Database("sqlite+pysqlite:///:memory:")
    db.create_schema()

    wecom = _CustomWeComChannel()
    enabled_model = _InspectingChatModel()
    enabled_service = ChatService(
        database=db,
        model=enabled_model,
        memory_enabled=False,
        notification_service=wecom,
    )
    enabled_service.answer(ChatRequest(question="你有哪些工具？"))
    assert len(enabled_model.respond_calls) == 1
    call_enabled = enabled_model.respond_calls[0]
    assert any(item["name"] == "send_feishu_notification" for item in call_enabled["tool_catalog"])
    assert call_enabled["capability_status"]["active_notification_channels"] == ["企业微信安全群"]
    assert call_enabled["capability_status"]["disabled_tools"]  # knowledge/learning/write still disabled

    disabled_model = _InspectingChatModel()
    disabled_service = ChatService(
        database=db,
        model=disabled_model,
        memory_enabled=False,
        notification_service=None,
    )
    disabled_service.answer(ChatRequest(question="能发通知吗？"))
    call_disabled = disabled_model.respond_calls[0]
    assert not any(item["name"] == "send_feishu_notification" for item in call_disabled["tool_catalog"])
    assert any(item["name"] == "send_feishu_notification" for item in call_disabled["capability_status"]["disabled_tools"])
    notif_cap = next(
        item for item in call_disabled["capability_status"]["capabilities"] if item["capability"] == "notification"
    )
    assert notif_cap["enabled"] is False
    assert "reason" in notif_cap

    # Backwards compatibility: 3-argument respond stubs still work without error
    legacy_service = ChatService(database=db, model=_LegacyThreeArgModel(), memory_enabled=False)
    legacy_resp = legacy_service.answer(ChatRequest(question="你好"))
    assert legacy_resp.answer == "legacy-ok"


def test_chat_endpoint_truthfully_reports_enabled_and_disabled_notification_capability() -> None:
    enabled_settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        internal_perception_token="cap-token",
        llm_provider="fake",
        auto_create_schema=True,
        feishu_notify_enabled=True,
        feishu_webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/test-hook",
    )
    with TestClient(create_app(enabled_settings)) as client:
        resp = client.post("/api/v1/agent/chat", json={"question": "你没有飞书通知工具吗"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["tool_trace"] == []
        assert "send_feishu_notification" in body["answer"]
        assert "飞书安全管理群" in body["answer"]

    disabled_settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        internal_perception_token="cap-token",
        llm_provider="fake",
        auto_create_schema=True,
        feishu_notify_enabled=False,
        feishu_webhook_url="",
    )
    with TestClient(create_app(disabled_settings)) as client:
        resp = client.post("/api/v1/agent/chat", json={"question": "你没有飞书通知工具吗"})
        assert resp.status_code == 200
        body = resp.json()
        assert body["tool_trace"] == []
        assert "send_feishu_notification" not in body["answer"]
        assert "未启用" in body["answer"]
