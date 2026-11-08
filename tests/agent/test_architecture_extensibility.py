"""Architectural verification tests for high cohesion, low coupling, no hardcoding, and extensibility."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, List, Tuple
from uuid import uuid4

from agent.contracts.chat import ToolDecision
from agent.contracts.query import ViolationRecord
from agent.core.config import Settings
from agent.db.base import Database
from agent.db.models import CvNodeModel, ViolationEventModel
from agent.domain.standards_guard import (
    contains_unsupported_standard_reference,
    guard_standard_references,
)
from agent.notifications import (
    CompositeNotificationService,
    NotificationPort,
)
from agent.rag.chroma_adapter import (
    EmbeddingProviderSpec,
    register_embedding_provider,
    supported_embedding_providers,
    validate_embedding_settings,
)
from agent.repositories.camera_management import CameraManagementRepository
from agent.repositories.knowledge import KnowledgeRepository
from agent.repositories.learning import LearningRepository
from agent.repositories.rectification_tasks import RectificationTaskRepository
from agent.repositories.violations import ViolationRepository
from agent.services.agent_write_actions import (
    AgentWriteActionService,
    WriteActionHandlerSpec,
)
from agent.services.camera_management import CameraManagementService
from agent.services.rectification_task_service import RectificationTaskService
from agent.services.report_pdf import render_report_html
from agent.services.ui_config_service import (
    DEFAULT_ASSISTANT_UI_CONFIG,
    UiConfigService,
)
from agent.tools.base import ToolContext
from perception.schemas.detection import (
    BoundingBox,
    DangerZone,
    TrackedPerson,
    ViolationEvent,
    ViolationSeverity,
    ViolationType,
)
from perception.tracking.state_machine import SafetyRulePlugin, WorkerSafetyMonitor


def test_standards_guard_ssot_consistency() -> None:
    evidence = "来源：JGJ 80-2016 建筑施工高处作业安全技术规范 第4.1.1条"
    assert not contains_unsupported_standard_reference(
        "依据《建筑施工高处作业安全技术规范》JGJ 80-2016 第4.1.1条执行。",
        evidence,
    )
    assert contains_unsupported_standard_reference(
        "依据《建筑施工扣件式钢管脚手架安全技术规范》JGJ 130-2011 执行。",
        evidence,
    )
    guard_standard_references(
        ["依据《建筑施工高处作业安全技术规范》第4.1.1条执行。"],
        [evidence],
    )


def test_report_html_renderer_cohesion() -> None:
    html = render_report_html(
        start="2026-11-01",
        end="2026-11-05",
        stats={"total": 5, "repeat_occurrences": 2, "by_type": {"NO_HELMET": 5}},
        content={"summary": "概述", "risk_analysis": "分析", "remediation": "整改"},
        citations=[{"title": "高处作业规范", "page_or_section": "第12页"}],
    )
    assert "施工安全报告" in html
    assert "有效违规事件：5" in html
    assert "高处作业规范 · 第12页" in html


def test_learning_and_camera_repositories_decoupling() -> None:
    db = Database("sqlite+pysqlite:///:memory:")
    db.create_schema()
    now = datetime.now(timezone.utc)

    with db.session() as session:
        cam_repo = CameraManagementRepository(session)
        cam_repo.add_node(
            CvNodeModel(
                node_id="node-01",
                display_name="Node 01",
                control_url="http://127.0.0.1:8090",
                control_token_encrypted="enc",
                capacity=4,
                is_online=True,
                last_heartbeat_at_utc=now - timedelta(seconds=15),
            )
        )
        learn_repo = LearningRepository(session)
        stats = learn_repo.aggregate_period_violations(now - timedelta(days=1), now)
        assert stats["total"] == 0

    # Configurable offline threshold: 15s elapsed < 30s default (not offline), but > 10s custom threshold (offline)
    service_default = CameraManagementService(db, "key", node_offline_threshold_seconds=30.0)
    service_strict = CameraManagementService(db, "key", node_offline_threshold_seconds=10.0)
    assert service_default.node_requires_recovery("node-01") is False
    assert service_strict.node_requires_recovery("node-01") is True


def test_embedding_provider_registry_extensibility() -> None:
    assert "openai_compatible" in supported_embedding_providers()
    validate_embedding_settings(
        provider="openai_compatible",
        model="bge-m3",
        api_key="test-key",
        base_url="https://embedding.example.com/v1",
        dimensions=1024,
        rag_enabled=True,
    )

    register_embedding_provider(
        "custom_local_mock",
        EmbeddingProviderSpec(
            name="custom_local_mock",
            build_function=lambda model, api_key, base_url, dims: (lambda input: [[0.1] * dims for _ in input]),
            default_collection=lambda model, dims: f"mock_{model}_{dims}",
        ),
    )
    assert "custom_local_mock" in supported_embedding_providers()
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        internal_perception_token="tok",
        llm_provider="fake",
        bind_host="127.0.0.1",
        port=8000,
        cors_origins=("http://localhost:5173",),
        rag_enabled=True,
        rag_embedding_provider="custom_local_mock",
        rag_embedding_model="any-custom-model",
        rag_embedding_dimensions=384,
    )
    settings.validate_for_runtime()


def test_composite_notification_port_extensibility() -> None:
    dispatched: list[tuple[str, str]] = []

    class DummyChannel:
        def __init__(self, channel_name: str) -> None:
            self.channel_name = channel_name
            self.is_configured = True

        def notify_violation_event(self, record: ViolationRecord, *, bypass_throttle: bool = False, sync: bool = False) -> dict[str, Any]:
            dispatched.append((self.channel_name, f"violation:{record.event_uuid}"))
            return {"ok": True, "channel": self.channel_name}

        def notify_rectification_created(self, task_payload: dict[str, Any], *, sync: bool = False) -> dict[str, Any]:
            dispatched.append((self.channel_name, "rect_created"))
            return {"ok": True}

        def notify_rectification_completed(self, task_payload: dict[str, Any], *, sync: bool = False) -> dict[str, Any]:
            dispatched.append((self.channel_name, "rect_completed"))
            return {"ok": True}

        def notify_report_confirmed(self, report: Any, *, sync: bool = False) -> dict[str, Any]:
            dispatched.append((self.channel_name, "report_confirmed"))
            return {"ok": True}

        def notify_training_published(self, training: Any, *, sync: bool = False) -> dict[str, Any]:
            dispatched.append((self.channel_name, "training_published"))
            return {"ok": True}

        def send_custom_briefing(self, title: str, summary_markdown: str, *, sync: bool = False) -> dict[str, Any]:
            dispatched.append((self.channel_name, f"briefing:{title}"))
            return {"ok": True, "channel": self.channel_name}

        def shutdown(self, wait: bool = False) -> None:
            dispatched.append((self.channel_name, "shutdown"))

    ch1 = DummyChannel("feishu")
    ch2 = DummyChannel("wecom")
    assert isinstance(ch1, NotificationPort)
    composite = CompositeNotificationService([ch1, ch2])
    assert composite.is_configured is True

    res = composite.send_custom_briefing("测试简报", "内容", sync=True)
    assert isinstance(res, dict) and res["ok"] is True
    composite.shutdown(wait=True)
    assert ("feishu", "briefing:测试简报") in dispatched
    assert ("wecom", "briefing:测试简报") in dispatched
    assert ("feishu", "shutdown") in dispatched
    assert ("wecom", "shutdown") in dispatched


def test_worker_safety_monitor_custom_rule_plugin() -> None:
    class CustomSpeedingRule:
        """Example custom safety rule plugin triggered without modifying WorkerSafetyMonitor."""

        def __init__(self) -> None:
            self.active_by_track: dict[int, ViolationEvent] = {}

        def evaluate_person(
            self,
            person: TrackedPerson,
            danger_zones: List[DangerZone],
            current_time: float,
            camera_id: str,
        ) -> Tuple[List[ViolationEvent], List[ViolationEvent]]:
            if person.track_id not in self.active_by_track:
                ev = ViolationEvent(
                    event_uuid=str(uuid4()),
                    track_id=person.track_id,
                    camera_id=camera_id,
                    violation_type=ViolationType.DWELL_TIMEOUT,
                    severity=ViolationSeverity.INFO,
                    start_time=current_time,
                    extra_details={"custom_rule": "CUSTOM_PLUGIN"},
                )
                self.active_by_track[person.track_id] = ev
                return [ev], []
            return [], []

        def cleanup_stale_tracks(
            self,
            active_track_ids: set[int],
            current_time: float,
        ) -> List[ViolationEvent]:
            closed: list[ViolationEvent] = []
            for tid in list(self.active_by_track):
                if tid not in active_track_ids:
                    ev = self.active_by_track.pop(tid)
                    ev.end_time = current_time
                    ev.status = "RESOLVED"
                    closed.append(ev)
            return closed

    plugin = CustomSpeedingRule()
    assert isinstance(plugin, SafetyRulePlugin)
    monitor = WorkerSafetyMonitor(camera_id="cam_test")
    monitor.register_rule(plugin)

    person = TrackedPerson(
        track_id=42,
        bbox=BoundingBox(x1=10, y1=10, x2=50, y2=100, conf=0.9, class_id=0, class_name="person", has_helmet=True),
        feet_point=(30.0, 100.0),
        has_helmet=True,
    )
    new_events, closed_events = monitor.process([person], [], current_time=1.0)
    assert len(new_events) == 1
    assert new_events[0].extra_details.get("custom_rule") == "CUSTOM_PLUGIN"
    assert len(closed_events) == 0

    # When track disappears, custom plugin cleanup is invoked automatically
    new_events_2, closed_events_2 = monitor.process([], [], current_time=2.0)
    assert len(new_events_2) == 0
    assert len(closed_events_2) == 1
    assert closed_events_2[0].status == "RESOLVED"


def test_rectification_task_repository_cohesion_and_decoupling() -> None:
    db = Database("sqlite+pysqlite:///:memory:")
    db.create_schema()
    now = datetime.now(timezone.utc)
    event_uuid = str(uuid4())

    with db.session() as session:
        session.add(
            ViolationEventModel(
                schema_version="1.0",
                event_uuid=event_uuid,
                camera_id="cam_01",
                monitor_session_id="sess_01",
                track_id=1,
                violation_type="NO_HELMET",
                severity="WARNING",
                status="ACTIVE",
                occurred_at_utc=now,
            )
        )
        session.flush()

        repo = RectificationTaskRepository(session)
        assert repo.event_exists(event_uuid) is True
        assert repo.event_exists(str(uuid4())) is False

        task = repo.create_task(
            event_uuid=event_uuid,
            title="整改安全帽违规",
            description="班组自查",
            owner="张安全员",
            due_at_utc=now + timedelta(days=2),
        )
        task_id = task.task_id
        session.flush()

        items, total = repo.list_tasks(owner="张", limit=10, offset=0)
        assert total == 1
        assert items[0].task_id == task_id
        assert items[0].violation_type == "NO_HELMET"

        detail = repo.get_task_detail(task_id)
        assert detail is not None
        assert detail.task.task_id == task_id
        assert detail.violation.event_uuid == event_uuid
        assert len(detail.audits) >= 1

        updated, resolved = repo.update_task(
            task_id=task_id,
            status="COMPLETED",
            note="已复核完成整改",
        )
        assert updated.status == "COMPLETED"
        assert resolved is True

        ev_after = session.get(ViolationEventModel, event_uuid)
        assert ev_after is not None
        assert ev_after.status == "RESOLVED"


def test_write_action_service_handler_registry_extensibility() -> None:
    db = Database("sqlite+pysqlite:///:memory:")
    db.create_schema()
    service = AgentWriteActionService(db, camera_management=None)

    def _propose_custom(svc: AgentWriteActionService, conv_id: str, dec: ToolDecision) -> tuple[str, dict[str, Any]]:
        return f"自定义操作：{dec.purpose}", {"custom_param": 42}

    def _exec_custom(svc: AgentWriteActionService, session: Any, payload: dict[str, Any]) -> tuple[dict[str, Any], None]:
        return {"executed_custom_param": payload["custom_param"] * 2}, None

    service.register_action_handler(
        WriteActionHandlerSpec(
            action_type="custom_extension_action",
            execution_mode="transactional",
            propose_fn=_propose_custom,
            execute_fn=_exec_custom,
        )
    )

    conv_id = "test-conv-custom"
    pending = service.propose(
        conv_id,
        ToolDecision(tool_name="custom_extension_action", purpose="测试架构可拓展性"),
    )
    assert pending.action_type == "custom_extension_action"
    assert "自定义操作" in pending.summary

    confirmed = service.confirm(pending.confirmation_id, conv_id)
    assert confirmed.status == "EXECUTED"
    assert confirmed.result["executed_custom_param"] == 84


def test_ui_config_default_fallback_and_tool_context_extensions() -> None:
    db = Database("sqlite+pysqlite:///:memory:")
    db.create_schema()

    with db.session() as session:
        ui_service = UiConfigService(session)
        default_cfg = ui_service.get_or_default()
        assert default_cfg.assistant_name == DEFAULT_ASSISTANT_UI_CONFIG.assistant_name
        assert len(default_cfg.quick_questions) > 0

    dummy_repo = ViolationRepository(None)  # type: ignore[arg-type]
    ctx = ToolContext(repository=dummy_repo, extensions={"custom_plugin": "v1"})
    assert ctx.extensions["custom_plugin"] == "v1"


def test_isp_base_notification_channel_minimal_subclass() -> None:
    from agent.notifications.protocol import BaseNotificationChannel, ViolationNotificationPort

    class SirenAlarmChannel(BaseNotificationChannel):
        def __init__(self) -> None:
            self.alarms: list[str] = []

        def notify_violation_event(self, record: ViolationRecord, *, bypass_throttle: bool = False, sync: bool = False) -> dict[str, Any]:
            self.alarms.append(record.event_uuid)
            return {"alarm": "sounded"}

    siren = SirenAlarmChannel()
    assert isinstance(siren, ViolationNotificationPort)
    assert isinstance(siren, NotificationPort)
    assert siren.is_configured is True
    assert siren.notify_rectification_created({}) is None
    assert siren.send_custom_briefing("t", "b") is None
    siren.shutdown()


def test_dip_knowledge_retriever_port() -> None:
    from agent.rag.chroma_adapter import KnowledgeChunk, KnowledgeRetrieverPort

    class InMemoryMockRetriever:
        def __init__(self) -> None:
            self.indexed: list[KnowledgeChunk] = []

        def index_chunks(self, chunks: list[KnowledgeChunk]) -> int:
            self.indexed.extend(chunks)
            return len(chunks)

        def delete_document_version(self, document_version_id: str, collection_name: str | None = None) -> None:
            self.indexed = [c for c in self.indexed if c.document_version_id != document_version_id]

        def query(self, query: str, top_k: int, document_type: str = "ACCIDENT_REPORT") -> list[KnowledgeChunk]:
            return self.indexed[:top_k]

        def collection_for_type(self, document_type: str) -> str:
            return "mock_collection"

    mock_retriever = InMemoryMockRetriever()
    assert isinstance(mock_retriever, KnowledgeRetrieverPort)


def test_ocp_tool_catalog_extensibility_and_intent_pruning() -> None:
    from agent.tools.base import AgentTool, ToolOutcome
    from agent.tools.catalog import DEFAULT_TOOL_CATALOG

    custom_tool = AgentTool(
        name="custom_drone_patrol",
        description="触发无人机现场巡查",
        parameters='{"drone_id": "string"}',
        handler=lambda dec, ctx: ToolOutcome(data={"patrol": "started"}),
    )

    extended_catalog = DEFAULT_TOOL_CATALOG.with_tools(custom_tool)
    assert extended_catalog.get("custom_drone_patrol").name == "custom_drone_patrol"

    ctx = ToolContext(repository=ViolationRepository(None))  # type: ignore[arg-type]
    weather_tools = extended_catalog.available_catalog(ctx, question="今天现场下雨吗？气温多少？", prune_by_intent=True)
    assert any(t["name"] == "get_current_weather" for t in weather_tools)
    assert not any(t["name"] == "create_training_task" for t in weather_tools)


def test_rectification_task_direct_execution_with_audit() -> None:
    db = Database("sqlite+pysqlite:///:memory:")
    db.create_schema()
    now = datetime.now(timezone.utc)
    event_uuid = str(uuid4())

    with db.session() as session:
        session.add(
            ViolationEventModel(
                schema_version="1.0",
                event_uuid=event_uuid,
                camera_id="cam_01",
                monitor_session_id="sess_01",
                track_id=1,
                violation_type="NO_HELMET",
                severity="WARNING",
                status="ACTIVE",
                occurred_at_utc=now,
            )
        )
        session.flush()

    write_service = AgentWriteActionService(db, camera_management=None)
    task_service = RectificationTaskService(db, write_service)

    from agent.contracts.rectification import RectificationTaskCreateRequest, RectificationTaskUpdateRequest

    task = task_service.create_task(
        RectificationTaskCreateRequest(
            conversation_id="conv-direct-01",
            event_uuid=event_uuid,
            title="直接创建整改任务",
            description="班组自查整改",
            owner="李工",
            due_at_utc=now + timedelta(days=3),
        )
    )
    assert task.title == "直接创建整改任务"
    assert task.owner == "李工"

    updated = task_service.update_task(
        task.task_id,
        RectificationTaskUpdateRequest(
            conversation_id="conv-direct-01",
            status="COMPLETED",
            note="现场已复核",
        ),
    )
    assert updated.status == "COMPLETED"


def test_outbox_store_dead_letter_and_requeue(tmp_path) -> None:
    from perception.services.event_publisher import OutboxStore, DEAD_LETTER_RETRY_AT

    store = OutboxStore(tmp_path / "outbox.db")
    ev_uuid = str(uuid4())
    store.enqueue(ev_uuid, {"test": "data"})
    store.record_failure(ev_uuid, "HTTP 422 Unprocessable", can_retry=False)

    dead_letters = store.get_dead_letter_events()
    assert len(dead_letters) == 1
    assert dead_letters[0]["event_uuid"] == ev_uuid
    assert dead_letters[0]["next_retry_at"] >= DEAD_LETTER_RETRY_AT

    requeued_count = store.requeue_dead_letters()
    assert requeued_count == 1
    assert len(store.get_dead_letter_events()) == 0
    pending = store.get_pending()
    assert len(pending) == 1
    assert pending[0]["event_uuid"] == ev_uuid


def test_compiled_safety_graph_threadsafe_reuse() -> None:
    from agent.graph.safety_graph import COMPILED_SAFETY_GRAPH

    db = Database("sqlite+pysqlite:///:memory:")
    db.create_schema()

    with db.session() as session:
        ctx = ToolContext(repository=ViolationRepository(session))
        res = COMPILED_SAFETY_GRAPH.invoke(
            {"operation": "statistics", "query": {}, "camera_id": None},
            config={"configurable": {"tool_context": ctx}},
        )
        assert res["operation"] == "statistics"
        assert res["result"]["total_violations"] == 0


def test_flexible_tool_max_calls_setting() -> None:
    s = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        internal_perception_token="tok",
        tool_max_calls=4,
        llm_provider="fake",
        auto_create_schema=True,
    )
    s.validate_for_runtime()
    assert s.tool_max_calls == 4


def test_redis_infrastructure_ports_and_fail_open_extensibility() -> None:
    from agent.infra import build_infra_container
    from agent.infra.ports import (
        CachePort,
        DistributedLockPort,
        EventStreamPort,
        RealtimeBroadcastPort,
        ThrottlePort,
    )

    # When REDIS_URL is invalid/unreachable, container must fail open with in-memory adapters
    s = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        internal_perception_token="tok",
        llm_provider="fake",
        auto_create_schema=True,
        redis_url="redis://127.0.0.1:59999/0",  # dead port
    )
    infra = build_infra_container(s)
    assert isinstance(infra.cache, CachePort)
    assert isinstance(infra.throttle, ThrottlePort)
    assert isinstance(infra.lock_service, DistributedLockPort)
    assert isinstance(infra.event_stream, EventStreamPort)
    assert isinstance(infra.broadcaster, RealtimeBroadcastPort)

    # In-memory fail-open works normally
    infra.cache.set_json("test_ns", "key", {"hello": "world"})
    assert infra.cache.get_json("test_ns", "key") == {"hello": "world"}

    with infra.lock_service.acquire("test_lock") as handle:
        assert handle.is_acquired is True



