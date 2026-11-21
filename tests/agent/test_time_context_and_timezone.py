from __future__ import annotations

from datetime import datetime, timezone
from types import SimpleNamespace
from uuid import uuid4

from agent.contracts.chat import ChatRequest, ToolDecision, ToolResult
from agent.contracts.event_v1 import EventStatus, SafetyViolationEventV1, ViolationSeverity, ViolationType
from agent.contracts.query import ViolationQuery, ViolationRecord
from agent.db.base import Database
from agent.db.models import ConversationTurnModel
from agent.domain.time_context import (
    enrich_record_local_times,
    format_local_datetime,
    format_request_time_context,
    normalize_to_utc,
)
from agent.llm.deepseek_adapter import DeepSeekChatModel
from agent.prompts import render_decision_prompt
from agent.repositories.violations import ViolationRepository
from agent.services.chat_service import ChatService
from agent.tools.base import ToolContext
from agent.tools.catalog import DEFAULT_TOOL_CATALOG


def test_normalize_to_utc_handles_offset_and_naive() -> None:
    aware = datetime.fromisoformat("2026-11-21T00:00:00+08:00")
    assert normalize_to_utc(aware) == datetime(2026, 11, 20, 16, 0, 0, tzinfo=timezone.utc)

    naive = datetime(2026, 11, 21, 0, 0, 0)
    assert normalize_to_utc(naive) == datetime(2026, 11, 21, 0, 0, 0, tzinfo=timezone.utc)
    assert normalize_to_utc(None) is None


def test_violation_query_normalizes_timezone_offset_to_utc() -> None:
    query = ViolationQuery(
        start_time_utc="2026-11-21T00:00:00+08:00",
        end_time_utc="2026-11-21T23:59:59+08:00",
    )
    assert query.start_time_utc == datetime(2026, 11, 20, 16, 0, 0, tzinfo=timezone.utc)
    assert query.end_time_utc == datetime(2026, 11, 21, 15, 59, 59, tzinfo=timezone.utc)


def test_tool_decision_normalizes_mixed_offset_timestamps() -> None:
    decision = ToolDecision(
        tool_name="create_rectification_task",
        violation_event_uuid=str(uuid4()),
        task_title="整改未佩戴安全帽",
        task_owner="张三",
        task_due_at_utc="2026-11-22T18:00:00+08:00",
        query=ViolationQuery(
            start_time_utc="2026-11-21T00:00:00+08:00",
            end_time_utc="2026-11-21T15:59:59Z",
        ),
        purpose="创建整改任务",
    )
    assert decision.task_due_at_utc == datetime(2026, 11, 22, 10, 0, 0, tzinfo=timezone.utc)
    assert decision.query.start_time_utc == datetime(2026, 11, 20, 16, 0, 0, tzinfo=timezone.utc)
    assert decision.query.end_time_utc == datetime(2026, 11, 21, 15, 59, 59, tzinfo=timezone.utc)


def test_request_time_context_and_local_datetime_cross_midnight() -> None:
    # 2026-11-20 18:15:00 UTC == 2026-11-21 02:15:00 Asia/Shanghai (Saturday)
    utc_dt = datetime(2026, 11, 20, 18, 15, 37, tzinfo=timezone.utc)
    ctx_text = format_request_time_context(utc_dt, "Asia/Shanghai")
    assert ctx_text == "[当前时间] 2026-11-21 02:15 (星期六, Asia/Shanghai, UTC+08:00)"

    local_str = format_local_datetime(utc_dt, "Asia/Shanghai")
    assert local_str == "2026-11-21 02:15:37 (星期六, Asia/Shanghai)"

    enriched = enrich_record_local_times(
        {"occurred_at_utc": "2026-11-20T18:15:00Z", "resolved_at_utc": None},
        (("occurred_at_utc", "occurred_at_local"), ("resolved_at_utc", "resolved_at_local")),
        "Asia/Shanghai",
    )
    assert enriched["occurred_at_utc"] == "2026-11-20T18:15:00Z"
    assert enriched["occurred_at_local"] == "2026-11-21 02:15:00 (星期六, Asia/Shanghai)"
    assert "resolved_at_local" not in enriched


def test_cross_midnight_violation_counted_for_beijing_today_in_sqlite() -> None:
    db = Database("sqlite:///:memory:")
    db.create_schema()
    event_uuid = uuid4()
    with db.session() as session:
        repo = ViolationRepository(session)
        repo.upsert_event_with_transition(
            SafetyViolationEventV1(
                event_uuid=event_uuid,
                camera_id="cam_01",
                monitor_session_id="sess_01",
                track_id=1,
                violation_type=ViolationType.NO_HELMET,
                severity=ViolationSeverity.WARNING,
                status=EventStatus.ACTIVE,
                occurred_at_utc=datetime(2026, 11, 20, 18, 15, 0, tzinfo=timezone.utc),
                duration_seconds=3.0,
            )
        )
        query = ViolationQuery(
            start_time_utc="2026-11-21T00:00:00+08:00",
            end_time_utc="2026-11-21T23:59:59+08:00",
        )
        stats = repo.get_statistics(query)
        assert stats.total_violations == 1

        ctx = ToolContext(repository=repo, extensions={"display_timezone": "Asia/Shanghai"})
        outcome = DEFAULT_TOOL_CATALOG.get("query_violations").execute(
            ToolDecision(tool_name="query_violations", query=query, purpose="查询今日违规"),
            ctx,
        )
        assert len(outcome.data) == 1
        assert outcome.data[0]["occurred_at_local"] == "2026-11-21 02:15:00 (星期六, Asia/Shanghai)"
        assert ViolationRecord.model_fields.keys() >= {"occurred_at_utc", "resolved_at_utc"}
        assert "occurred_at_local" not in ViolationRecord.model_fields


def test_deepseek_adapter_keeps_system_static_and_prepends_time_to_user_message() -> None:
    model = DeepSeekChatModel.__new__(DeepSeekChatModel)
    model.model_name = "deepseek-test"

    decide_calls: list[list] = []
    answer_calls: list[list] = []

    class _ClientStub:
        def __init__(self, sink: list[list], content: str) -> None:
            self._sink = sink
            self._content = content

        def invoke(self, messages: list):
            self._sink.append(messages)
            return SimpleNamespace(content=self._content)

    model._client = _ClientStub(decide_calls, '{"tool_name": null}')
    model._answer_client = _ClientStub(answer_calls, "今天暂无违规。")

    time_ctx = "[当前时间] 2026-11-21 23:31 (星期六, Asia/Shanghai, UTC+08:00)"
    decision = model.decide(
        "今天有多少违规？",
        previous_results=[],
        memory_context="历史摘要",
        tool_catalog=[{"name": "get_violation_statistics", "description": "统计", "parameters": "query"}],
        request_time_context=time_ctx,
    )
    assert decision is None
    assert "[当前时间]" not in decide_calls[0][0].content
    assert decide_calls[0][1].content.index("历史摘要") < decide_calls[0][1].content.index(time_ctx)
    assert decide_calls[0][1].content.index(time_ctx) < decide_calls[0][1].content.index("用户问题：今天有多少违规？")

    answer = model.respond(
        "今天有多少违规？",
        results=[ToolResult(tool_name="get_violation_statistics", data={"total_violations": 0})],
        memory_context="历史摘要",
        request_time_context=time_ctx,
    )
    assert answer == "今天暂无违规。"
    assert "[当前时间]" not in answer_calls[0][0].content
    assert answer_calls[0][1].content.index(time_ctx) < answer_calls[0][1].content.index("用户问题：今天有多少违规？")


def test_chat_service_freezes_time_context_and_keeps_memory_clean() -> None:
    db = Database("sqlite:///:memory:")
    db.create_schema()

    seen_decide_times: list[str] = []
    seen_respond_times: list[str] = []

    class _SpyModel:
        model_name = "spy-model"

        def decide(self, question, previous_results, memory_context="", tool_catalog=(), request_time_context=""):
            seen_decide_times.append(request_time_context)
            if not previous_results:
                return ToolDecision(tool_name="get_violation_statistics", purpose="查询统计")
            return None

        def respond(
            self,
            question,
            results,
            memory_context="",
            tool_catalog=(),
            capability_status=None,
            response_locale="zh-CN",
            request_time_context="",
        ):
            seen_respond_times.append(request_time_context)
            return "查询完成。"

        def generate_structured(self, instruction, context, response_locale="zh-CN"):
            return {}

    service = ChatService(db, _SpyModel(), display_timezone="Asia/Shanghai")
    resp = service.answer(ChatRequest(question="今天有几条违规？", conversation_id="conv-time-test"))
    assert resp.answer == "查询完成。"
    assert len(seen_decide_times) == 2
    assert seen_decide_times[0].startswith("[当前时间]")
    assert "Asia/Shanghai" in seen_decide_times[0]
    assert seen_decide_times[0] == seen_decide_times[1] == seen_respond_times[0]

    with db.session() as session:
        turn = session.query(ConversationTurnModel).filter_by(conversation_id="conv-time-test").one()
        assert turn.user_text == "今天有几条违规？"
        assert "[当前时间]" not in turn.user_text


def test_decision_prompt_documents_offset_iso_support() -> None:
    prompt = render_decision_prompt()
    assert "+08:00" in prompt
    assert "【当前时间】" in prompt
    assert "## 输出与格式" in prompt
    assert "## 参数与时间规范" in prompt
    assert "## 工具路由规则" in prompt
    assert "## 多步终止条件" in prompt
    assert '{"tool_name": null, "purpose":' in prompt


def test_prompt_engineering_rules_consistency() -> None:
    from agent.prompts import load_prompt

    structured = load_prompt("structured_system")
    assert "Markdown" in structured
    assert "JSON" in structured

    training = load_prompt("training_generation", question_count=5)
    assert "资料依据不足" in training
    assert "合法 JSON" in training

    weekly = load_prompt("weekly_advice")
    assert "advice" in weekly

    response = load_prompt("response")
    assert "*_local" in response
    assert "分点列出" in response


def test_pending_action_answer_uses_local_display_timezone() -> None:
    from agent.contracts.actions import PendingActionResponse
    from agent.domain.time_context import format_local_time_short
    from agent.graph.chat_graph import build_compiled_chat_graph

    expires_utc = datetime(2026, 11, 20, 18, 15, 0, tzinfo=timezone.utc)
    assert format_local_time_short(expires_utc, "Asia/Shanghai") == "02:15 (Asia/Shanghai)"

    class _WriteProposeModel:
        model_name = "write-propose"

        def decide(self, question, previous_results, memory_context="", tool_catalog=(), request_time_context=""):
            return ToolDecision(tool_name="start_monitoring", camera_id="A01", purpose="启动监控")

        def respond(self, question, results, memory_context="", **kwargs):
            return "unused"

        def generate_structured(self, instruction, context, response_locale="zh-CN"):
            return {}

    class _WriteServiceStub:
        def propose(self, conversation_id, decision):
            return PendingActionResponse(
                confirmation_id="c1",
                action_type=decision.tool_name,
                summary="启动监控：A01",
                expires_at_utc=expires_utc,
                status="PENDING",
            )

    db = Database("sqlite:///:memory:")
    db.create_schema()
    with db.session() as session:
        ctx = ToolContext(
            repository=ViolationRepository(session),
            write_action_service=_WriteServiceStub(),
            conversation_id="conv-local-expiry",
            extensions={"display_timezone": "Asia/Shanghai"},
        )
        graph = build_compiled_chat_graph(_WriteProposeModel(), default_context=ctx)
        out = graph.invoke({"question": "启动监控", "conversation_id": "conv-local-expiry", "tool_results": [], "tool_trace": [], "evidence": [], "knowledge_citations": []})
        assert "02:15 (Asia/Shanghai)" in out["answer"]
        assert "UTC" not in out["answer"]


def test_create_training_allows_fewer_well_supported_questions(tmp_path) -> None:
    import pytest
    from agent.contracts.learning import TrainingCreate
    from agent.db.models import SafetyReportModel
    from agent.services.learning_service import LearningService

    db = Database("sqlite:///:memory:")
    db.create_schema()
    report_id = str(uuid4())
    with db.session() as session:
        session.add(
            SafetyReportModel(
                report_id=report_id,
                period_start_utc=datetime(2026, 11, 16, 0, 0, tzinfo=timezone.utc),
                period_end_utc=datetime(2026, 11, 21, 0, 0, tzinfo=timezone.utc),
                status="CONFIRMED",
                statistics_json={"total": 2, "by_type": {"NO_HELMET": 2}},
                citations_json=[],
                content_json={"summary": "概述", "risk_analysis": "未戴安全帽风险", "remediation": "立即整改"},
                created_at_utc=datetime(2026, 11, 21, 0, 0, tzinfo=timezone.utc),
            )
        )

    class _PartialTrainingModel:
        model_name = "partial-training"

        def decide(self, *args, **kwargs):
            return None

        def respond(self, *args, **kwargs):
            return ""

        def generate_structured(self, instruction, context, response_locale="zh-CN"):
            return {
                "material": "培训材料正文。\n资料依据不足，仅生成 2 道题。",
                "questions": [
                    {"stem": "题1", "options": ["A", "B", "C", "D"], "answer": 0, "evidence": "未戴安全帽风险"},
                    {"stem": "题2", "options": ["A", "B", "C", "D"], "answer": 1, "evidence": "立即整改"},
                ],
            }

    class _KnowledgeStub:
        rag_manager = None

    service = LearningService(
        database=db,
        knowledge=_KnowledgeStub(),  # type: ignore[arg-type]
        model=_PartialTrainingModel(),
        report_directory=str(tmp_path),
        public_base_url="http://127.0.0.1:5173",
    )
    created = service.create_training(TrainingCreate(report_id=report_id, title="专项培训", target_count=10, question_count=5))
    assert created.question_count == 2
    assert len(created.questions) == 2

    class _EmptyTrainingModel(_PartialTrainingModel):
        def generate_structured(self, instruction, context, response_locale="zh-CN"):
            return {"material": "材料", "questions": []}

    service.model = _EmptyTrainingModel()
    with pytest.raises(ValueError, match="培训内容或题目数量不完整"):
        service.create_training(TrainingCreate(report_id=report_id, title="空题培训", target_count=10, question_count=5))

