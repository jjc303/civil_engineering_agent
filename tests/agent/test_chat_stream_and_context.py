from __future__ import annotations

import asyncio
import json

from fastapi.testclient import TestClient

from agent.contracts.chat import ChatRequest, PageContext
from agent.core.config import Settings
from agent.db.base import Database
from agent.llm.fake_adapter import FakeChatModel
from agent.main import create_app
from agent.services.chat_service import ChatService, format_page_context
from agent.services.sse_serializer import format_sse_comment, format_sse_event
from agent.services.standards_context import build_standards_context


def _test_settings() -> Settings:
    return Settings(
        database_url="sqlite:///:memory:",
        internal_perception_token="test-internal-token",
        auto_create_schema=True,
        llm_provider="fake",
        rag_enabled=False,
    )


def test_format_page_context_sanitizes_newlines() -> None:
    text = format_page_context(
        PageContext(
            route_key="zones",
            route_title="危险区域\n标定",
            camera_id="cam-01\r\n",
            event_uuid="evt-123",
        )
    )
    assert "危险区域 标定 (zones)" in text
    assert "焦点摄像头：cam-01" in text
    assert "焦点违规事件：evt-123" in text
    assert "\r" not in text


def test_build_standards_context_without_knowledge_service() -> None:
    result = build_standards_context(None, "安全帽要求", 4)
    assert result.error_code is None
    assert result.citations == []
    assert "未检索到相关片段" in result.context_text


def test_sse_serializer_formats_frames() -> None:
    frame = format_sse_event("stage", {"stage": "selecting_tool", "tool_name": None})
    assert frame.startswith("event: stage\ndata: ")
    assert frame.endswith("\n\n")
    assert json.loads(frame.split("data: ", 1)[1].strip())["stage"] == "selecting_tool"
    assert format_sse_comment() == ": keepalive\n\n"


def test_chat_stream_emits_stages_and_completed_response() -> None:
    database = Database("sqlite:///:memory:")
    database.create_schema()
    service = ChatService(database=database, model=FakeChatModel(), memory_enabled=False)

    async def collect():
        items = []
        async for event in service.answer_stream(
            ChatRequest(
                question="查看所有摄像头状态",
                page_context=PageContext(route_key="dashboard", route_title="安全监控看板"),
            )
        ):
            items.append(event)
        return items

    events = asyncio.run(collect())
    stages = [item.stage for item in events]
    assert "retrieving_standards" in stages
    assert "selecting_tool" in stages
    assert "executing_tool" in stages
    assert "responding" in stages
    assert stages[-1] == "completed"
    assert events[-1].response is not None
    assert events[-1].response.tool_trace


def test_api_ui_config_includes_mascot_profile_and_chat_stream() -> None:
    app = create_app(_test_settings())
    with TestClient(app) as client:
        ui_res = client.get("/api/v1/agent/ui-config")
        assert ui_res.status_code == 200
        ui_body = ui_res.json()
        assert ui_body["mascot_profile"]["enabled"] is True
        assert ui_body["mascot_profile"]["persona_name"] == "安小盾"

        stream_res = client.post(
            "/api/v1/agent/chat/stream",
            json={
                "question": "查看所有摄像头状态",
                "page_context": {"route_key": "cameras", "route_title": "摄像头与 CV 节点"},
            },
        )
        assert stream_res.status_code == 200
        assert "event: completed" in stream_res.text
        assert "text/event-stream" in stream_res.headers["content-type"]
