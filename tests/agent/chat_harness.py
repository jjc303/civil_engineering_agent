"""Characterization harness for the chat tool pipeline.

Drives the public ``ChatService.answer`` entry point with a scripted model and
deterministic fake services, recording everything observable: the tool catalog
offered to the model, the arguments passed to backing services, and the final
``ChatResponse``. Golden files are produced from the pre-refactor code and act
as a behavioural lock while internals are restructured.

Regenerate (only when an intentional behaviour change is approved)::

    UPDATE_GOLDEN=1 pytest tests/agent/test_chat_tool_characterization.py
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Sequence

import httpx

from agent.contracts.actions import PendingActionResponse
from agent.contracts.chat import ChatRequest, KnowledgeCitation, ToolDecision, ToolResult
from agent.contracts.learning import ReportContent, ReportResponse, TrainingQuestion, TrainingResponse
from agent.db.base import Database
from agent.db.models import CameraStatusModel, ManagedCameraModel, ViolationEventModel
from agent.services.agent_write_actions import AgentWriteActionError
from agent.services.chat_service import ChatService

GOLDEN_DIR = Path(__file__).parent / "golden"
FIXED = datetime(2026, 9, 25, 12, 30, tzinfo=timezone.utc)
EVENT_UUID = "11111111-1111-4111-8111-111111111111"
REPORT_ID = "22222222-2222-4222-8222-222222222222"
TRAINING_ID = "33333333-3333-4333-8333-333333333333"


# --------------------------------------------------------------------- fakes
class ScriptedModel:
    model_name = "scripted"

    def __init__(self, decisions: Sequence[dict[str, Any] | None | Exception], answer: str | None = None) -> None:
        self._decisions = list(decisions)
        self._answer = answer
        self.calls: list[dict[str, Any]] = []

    def decide(self, question, previous_results, memory_context="", tool_catalog=()):
        self.calls.append({
            "kind": "decide",
            "previous": [item.model_dump(mode="json") for item in previous_results],
            "memory_context": memory_context,
            "catalog": [dict(item) for item in tool_catalog],
        })
        step = self._decisions.pop(0) if self._decisions else None
        if isinstance(step, Exception):
            raise step
        return None if step is None else ToolDecision.model_validate(step)

    def respond(self, question, results: Sequence[ToolResult], memory_context=""):
        self.calls.append({"kind": "respond", "results": [r.model_dump(mode="json") for r in results], "memory_context": memory_context})
        return self._answer or "ANSWER[" + ",".join(r.tool_name for r in results) + "]"

    def generate_structured(self, instruction, context):  # pragma: no cover - unused by chat
        raise AssertionError("not used")


class Recorder:
    def __init__(self) -> None:
        self.calls: list[list[Any]] = []

    def record(self, *items: Any) -> None:
        self.calls.append([_jsonable(item) for item in items])


class FakeKnowledge:
    def __init__(self, recorder: Recorder) -> None:
        self.rec = recorder

    def search(self, query, top_k):
        self.rec.record("knowledge.search", query, top_k)
        return ([{"title": "事故报告A", "content": "高处坠落经过", "page_or_section": "第2页"}],
                [KnowledgeCitation(document_id="doc-a", version_no=1, title="事故报告A", page_or_section="第2页", chunk_id="c1", relevance_score=0.9)])

    def search_standards(self, query, top_k):
        self.rec.record("knowledge.search_standards", query, top_k)
        return ([{"title": "施工安全规范", "page_or_section": "3.1", "source_label": "内部", "validity_status": "CURRENT", "content": "进入现场必须佩戴安全帽"}],
                [KnowledgeCitation(document_id="std-1", version_no=1, title="施工安全规范", page_or_section="3.1", chunk_id="s1", relevance_score=0.8, document_type="STANDARD")])

    def standard_catalog(self):
        self.rec.record("knowledge.standard_catalog")
        return [("施工安全规范", "已索引", "CURRENT"), ("旧规程", "未索引", "SUPERSEDED")]


class FakeWriteActions:
    def __init__(self, recorder: Recorder, fail: bool = False) -> None:
        self.rec, self.fail = recorder, fail

    def propose(self, conversation_id, decision: ToolDecision):
        self.rec.record("write.propose", conversation_id, decision.model_dump(mode="json", exclude_none=True))
        if self.fail:
            raise AgentWriteActionError("目标不存在")
        return PendingActionResponse(confirmation_id="confirm-1", action_type=decision.tool_name, summary=f"摘要:{decision.tool_name}", expires_at_utc=FIXED)


def _report() -> ReportResponse:
    return ReportResponse(report_id=REPORT_ID, period_start_utc=FIXED, period_end_utc=FIXED.replace(day=27), status="CONFIRMED",
                          statistics={"total": 3}, citations=[], content=ReportContent(summary="本周违规3起", risk_analysis="风险", remediation="整改"),
                          pdf_url="/api/v1/learning/reports/r/pdf", created_at_utc=FIXED)


def _training() -> TrainingResponse:
    return TrainingResponse(task_id=TRAINING_ID, report_id=REPORT_ID, status="DRAFT", title="安全帽培训", target_count=10, question_count=1,
                            pass_score=80, selected_documents=[], material="学习材料" * 5,
                            questions=[TrainingQuestion(stem="题", options=["a", "b"], answer=0)], public_url=None)


class FakeLearning:
    def __init__(self, recorder: Recorder) -> None:
        self.rec = recorder

    def weekly_overview(self):
        self.rec.record("learning.weekly_overview")
        return {"total": 3}

    def weekly_insights(self):
        self.rec.record("learning.weekly_insights")
        return {"advice": "加强巡查"}

    def list_reports(self):
        self.rec.record("learning.list_reports")
        return [_report()]

    def get_report(self, report_id):
        self.rec.record("learning.get_report", report_id)
        return _report()

    def list_training(self):
        self.rec.record("learning.list_training")
        return [_training()]

    def get_training(self, training_id):
        self.rec.record("learning.get_training", training_id)
        return _training()

    def training_statistics(self, training_id):
        self.rec.record("learning.training_statistics", training_id)
        return {"target_count": 10, "submissions": [{"worker": str(i)} for i in range(25)]}


class FakeNotification:
    is_configured = True

    def __init__(self, recorder: Recorder) -> None:
        self.rec = recorder

    def send_custom_briefing(self, title, body, sync=False):
        self.rec.record("notify.send_custom_briefing", title, body, sync)
        return {"ok": True}


class _WeatherResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class FakeWeatherClient:
    def __init__(self, *args, **kwargs):
        pass

    def get(self, url, *, params):
        if "geocoding" in url:
            return _WeatherResponse({"results": [{"name": "北京市", "country": "中国", "latitude": 39.9, "longitude": 116.4}]})
        return _WeatherResponse({"current": {"time": "2026-09-25T20:00", "temperature_2m": 21.5, "weather_code": 1, "wind_speed_10m": 9.0}})

    def close(self):
        pass


# ------------------------------------------------------------------ fixtures
def seeded_database() -> Database:
    database = Database("sqlite+pysqlite:///:memory:")
    database.create_schema()
    with database.session() as session:
        session.add(ViolationEventModel(
            event_uuid=EVENT_UUID, schema_version="1.0", camera_id="A01", monitor_session_id="s1", track_id=7,
            violation_type="NO_HELMET", severity="CRITICAL", status="ACTIVE", zone_id="z1", zone_name="塔吊区",
            occurred_at_utc=FIXED, duration_seconds=4.0, snapshot_uri="snapshots/a.jpg", extra_details={},
        ))
        session.add(CameraStatusModel(camera_id="A01", monitor_session_id="s1", is_online=True, fps=25.0, processed_frame_id=9,
                                      active_workers_count=3, reported_at_utc=FIXED, extra_details={}))
        session.add(ManagedCameraModel(camera_id="A01", display_name="东门", node_id="n1", source_type="RTSP",
                                       source_uri_encrypted="x", source_uri_masked="rtsp://***", desired_state="RUNNING"))
    return database


FLAG_SETS: dict[str, dict[str, bool]] = {
    "none": {},
    "knowledge": {"knowledge": True},
    "write": {"write": True},
    "learning_write": {"learning": True, "write": True},
    "full": {"knowledge": True, "write": True, "learning": True, "notification": True},
}


def run_chat(decisions, *, flags: dict[str, bool], question: str = "问题", answer: str | None = None,
             write_fails: bool = False, max_tool_calls: int = 2, monkeypatch=None) -> dict[str, Any]:
    if monkeypatch is not None:
        monkeypatch.setattr(httpx, "Client", FakeWeatherClient)
    recorder = Recorder()
    model = ScriptedModel(decisions, answer)
    service = ChatService(
        database=seeded_database(),
        model=model,
        max_tool_calls=max_tool_calls,
        memory_enabled=False,
        knowledge_service=FakeKnowledge(recorder) if flags.get("knowledge") else None,
        write_action_service=FakeWriteActions(recorder, write_fails) if flags.get("write") else None,
        standards_top_k=4,
        learning_service=FakeLearning(recorder) if flags.get("learning") else None,
        notification_service=FakeNotification(recorder) if flags.get("notification") else None,
    )
    response = service.answer(ChatRequest(question=question, conversation_id="conv-1"))
    body = response.model_dump(mode="json")
    body.pop("request_id")
    for item in body["tool_trace"]:
        item.pop("duration_ms")
    return {"response": body, "service_calls": recorder.calls, "model_calls": model.calls}


# ------------------------------------------------------------------- golden
def _jsonable(value: Any) -> Any:
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


def assert_golden(name: str, actual: Any) -> None:
    path = GOLDEN_DIR / f"{name}.json"
    actual = _jsonable(actual)
    if os.getenv("UPDATE_GOLDEN") == "1" or not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(actual, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        if os.getenv("UPDATE_GOLDEN") != "1":
            raise AssertionError(f"golden file {path.name} was missing and has been created; re-run")
        return
    expected = json.loads(path.read_text(encoding="utf-8"))
    assert actual == expected, f"behaviour drift against golden/{path.name}"
