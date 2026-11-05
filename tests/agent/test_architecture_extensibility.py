"""Architectural verification tests for high cohesion, low coupling, no hardcoding, and extensibility."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, List, Tuple
from uuid import uuid4

from agent.contracts.query import ViolationRecord
from agent.core.config import Settings
from agent.db.base import Database
from agent.db.models import CvNodeModel
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
from agent.repositories.learning import LearningRepository
from agent.services.camera_management import CameraManagementService
from agent.services.report_pdf import render_report_html
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
