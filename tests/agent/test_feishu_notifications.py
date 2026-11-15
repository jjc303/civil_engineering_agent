from __future__ import annotations

import base64
from concurrent.futures import Future
from datetime import datetime, timedelta, timezone
import hashlib
import hmac
from typing import Any
from uuid import uuid4

import fakeredis
from fastapi.testclient import TestClient
import httpx
import pytest

from agent.contracts.event_v1 import SafetyViolationEventV1
from agent.contracts.learning import ReportContent, ReportResponse, TrainingResponse
from agent.contracts.query import ViolationRecord
from agent.core.config import Settings
from agent.db.base import Database
from agent.infra.messaging import RedisEventStreamAdapter
from agent.infra.redis_client import KeyBuilder
from agent.main import create_app
from agent.notifications import (
    BaseNotificationChannel,
    CallableWebhookTransport,
    CompositeNotificationService,
    FeishuCardBuilder,
    FeishuNotificationService,
    NotificationLinkBuilder,
    create_notification_service,
)
from agent.notifications.feishu_service import AlertThrottle
from agent.services.agent_write_actions import AgentWriteActionService
from agent.services.perception_service import PerceptionService
from agent.repositories.violations import ViolationRepository
from agent.tools.base import ToolContext
from agent.tools.catalog import DEFAULT_TOOL_CATALOG


def _make_violation_record(
    *,
    event_uuid: str | None = None,
    camera_id: str = "camera-a01",
    violation_type: str = "NO_HELMET",
    severity: str = "CRITICAL",
    status: str = "ACTIVE",
    zone_id: str | None = "zone-a",
    zone_name: str | None = "基坑南侧通道",
    occurred_at_utc: datetime | None = None,
) -> ViolationRecord:
    return ViolationRecord(
        event_uuid=event_uuid or str(uuid4()),
        camera_id=camera_id,
        monitor_session_id="session-20261103-a01",
        track_id=18,
        violation_type=violation_type,
        severity=severity,
        status=status,
        zone_id=zone_id,
        zone_name=zone_name,
        occurred_at_utc=occurred_at_utc or datetime(2026, 11, 3, 2, 30, 0, tzinfo=timezone.utc),
        resolved_at_utc=None,
        duration_seconds=3.5,
        snapshot_uri="snapshots/20261103/evidence.jpg",
        model_name="yolov8s",
        model_version="2026.11",
        extra_details={},
    )


def test_violation_record_normalize_utc_preserves_aware_datetime() -> None:
    aware_utc = _make_violation_record(occurred_at_utc=datetime(2026, 11, 3, 2, 30, 0, tzinfo=timezone.utc))
    assert aware_utc.occurred_at_utc == datetime(2026, 11, 3, 2, 30, 0, tzinfo=timezone.utc)

    plus_eight = timezone(timedelta(hours=8))
    aware_cst = _make_violation_record(occurred_at_utc=datetime(2026, 11, 3, 10, 30, 0, tzinfo=plus_eight))
    assert aware_cst.occurred_at_utc == datetime(2026, 11, 3, 2, 30, 0, tzinfo=timezone.utc)

    naive = _make_violation_record(occurred_at_utc=datetime(2026, 11, 3, 2, 30, 0))
    assert naive.occurred_at_utc == datetime(2026, 11, 3, 2, 30, 0, tzinfo=timezone.utc)


def test_feishu_card_builder_all_templates() -> None:
    record = _make_violation_record()
    violation_card = FeishuCardBuilder.build_violation_alert_card(
        record,
        web_base_url="http://localhost:5173",
    )
    assert violation_card["header"]["template"] == "red"
    assert "未佩戴安全帽" in violation_card["header"]["title"]["content"]
    assert "2026-11-03 10:30:00" in violation_card["elements"][0]["fields"][4]["text"]["content"]
    assert "JGJ 80-2016" in violation_card["elements"][2]["text"]["content"]

    rect_created_card = FeishuCardBuilder.build_rectification_created_card(
        {
            "task_id": "task-uuid-0001",
            "event_uuid": record.event_uuid,
            "title": "吊装作业区清退",
            "owner": "张工",
            "due_at_utc": "2026-11-03T03:00:00+00:00",
            "description": "立即设置警戒隔离带并疏散无关人员",
        },
        web_base_url="http://localhost:5173",
    )
    assert rect_created_card["header"]["template"] == "blue"
    assert "整改督办" in rect_created_card["header"]["title"]["content"]

    rect_done_card = FeishuCardBuilder.build_rectification_completed_card(
        {
            "task_id": "task-uuid-0001",
            "event_uuid": record.event_uuid,
            "title": "吊装作业区清退",
            "owner": "张工",
            "completed_at_utc": "2026-11-03T02:45:00+00:00",
            "note": "已完成警戒隔离并复核现场无人员滞留",
        },
        web_base_url="http://localhost:5173",
    )
    assert rect_done_card["header"]["template"] == "green"
    assert "隐患销项" in rect_done_card["header"]["title"]["content"]

    now = datetime(2026, 11, 3, 9, 0, 0, tzinfo=timezone.utc)
    report_model = ReportResponse(
        report_id="report-uuid-0001",
        period_start_utc=now,
        period_end_utc=now,
        status="CONFIRMED",
        statistics={"total": 2, "repeat_occurrences": 1},
        citations=[],
        content=ReportContent(
            summary="今日累计发现2起安全帽违规，均已闭环。",
            risk_analysis="基坑入口安全帽佩戴意识薄弱",
            remediation="加强班前安全交底与门禁核查",
        ),
        pdf_url="/api/v1/learning/reports/report-uuid-0001/pdf",
        created_at_utc=now,
    )
    report_card = FeishuCardBuilder.build_report_confirmed_card(
        report_model,
        web_base_url="http://localhost:5173",
    )
    assert report_card["header"]["template"] == "purple"
    assert "安全周报" in report_card["header"]["title"]["content"]

    training_model = TrainingResponse(
        task_id="training-uuid-0001",
        report_id="report-uuid-0001",
        title="起重吊装与临边防护专项交底",
        status="PUBLISHED",
        selected_documents=[],
        material="针对吊装半径内严禁穿行及临边安全带系挂规范进行强化培训。",
        questions=[],
        question_count=5,
        pass_score=80,
        target_count=25,
        public_url="http://localhost:5173/learn/tok-123",
        qr_url="/api/v1/learning/training/training-uuid-0001/qr",
    )
    training_card = FeishuCardBuilder.build_training_published_card(
        training_model,
        web_base_url="http://localhost:5173",
    )
    assert training_card["header"]["template"] == "turquoise"
    assert "全员安全教育" in training_card["header"]["title"]["content"]

    briefing_card = FeishuCardBuilder.build_custom_briefing_card(
        title="AI 安全助手主动巡检通报",
        summary_markdown="过去1小时内1号塔吊区域连续出现2次危险区闯入告警，建议增派专职安全员现场值守。",
        web_base_url="http://localhost:5173",
    )
    assert briefing_card["header"]["template"] == "wathet"
    assert "安全智能体通报" in briefing_card["header"]["title"]["content"]


def test_notification_link_builder_avoids_duplicate_subpath() -> None:
    links = NotificationLinkBuilder("http://47.95.234.149/helmet", app_base_path="/helmet")
    assert links.resolve_resource_url("/helmet/api/v1/learning/reports/rep-1/pdf") == (
        "http://47.95.234.149/helmet/api/v1/learning/reports/rep-1/pdf"
    )
    assert links.resolve_resource_url("/api/v1/learning/reports/rep-1/pdf") == (
        "http://47.95.234.149/helmet/api/v1/learning/reports/rep-1/pdf"
    )
    assert links.route("rectification_tasks", event_uuid="ev-1") == (
        "http://47.95.234.149/helmet/rectification-tasks?event_uuid=ev-1"
    )

    now = datetime(2026, 11, 3, 9, 0, 0, tzinfo=timezone.utc)
    report_model = ReportResponse(
        report_id="rep-subpath-1",
        period_start_utc=now,
        period_end_utc=now,
        status="CONFIRMED",
        statistics={"total": 1, "repeat_occurrences": 0},
        citations=[],
        content=ReportContent(summary="汇总", risk_analysis="分析", remediation="整改"),
        pdf_url="/helmet/api/v1/learning/reports/rep-subpath-1/pdf",
        created_at_utc=now,
    )
    card = FeishuCardBuilder(link_builder=links).report_confirmed(report_model)
    pdf_button_url = card["elements"][3]["actions"][0]["url"]
    assert pdf_button_url == "http://47.95.234.149/helmet/api/v1/learning/reports/rep-subpath-1/pdf"


def test_alert_throttle_sliding_window() -> None:
    throttle = AlertThrottle(cooldown_seconds=60)
    assert throttle.should_send("cam-1", "NO_HELMET", "zone-1") is True
    assert throttle.should_send("cam-1", "NO_HELMET", "zone-1") is False
    # Different camera or violation type is allowed immediately
    assert throttle.should_send("cam-2", "NO_HELMET", "zone-1") is True
    assert throttle.should_send("cam-1", "DANGER_ZONE_INTRUSION", "zone-1") is True
    # Reset clears cooldown
    throttle.reset()
    assert throttle.should_send("cam-1", "NO_HELMET", "zone-1") is True


def test_feishu_signature_and_severity_filtering() -> None:
    sent_envelopes: list[dict[str, Any]] = []
    service = FeishuNotificationService(
        "https://open.feishu.cn/open-apis/bot/v2/hook/mock-token",
        webhook_secret="my-secret-key",
        enabled=True,
        cooldown_seconds=60,
        min_severity="CRITICAL",
        transport=CallableWebhookTransport(
            lambda url, payload, timeout: sent_envelopes.append(payload) or {"code": 0, "msg": "success"}
        ),
    )
    try:
        # Verify HMAC-SHA256 signature matches official Feishu specification
        ts = "1730600000"
        expected_str = f"{ts}\nmy-secret-key"
        expected_sign = base64.b64encode(
            hmac.new(expected_str.encode("utf-8"), digestmod=hashlib.sha256).digest()
        ).decode("utf-8")
        assert service.compute_signature(ts, "my-secret-key") == expected_sign

        # WARNING event should be filtered out when min_severity == CRITICAL
        warn_record = _make_violation_record(severity="WARNING")
        assert service.notify_violation_event(warn_record) is None

        # CRITICAL event should be dispatched
        crit_record = _make_violation_record(severity="CRITICAL")
        future = service.notify_violation_event(crit_record)
        assert isinstance(future, Future)
        res = future.result(timeout=5.0)
        assert res["ok"] is True
    finally:
        service.shutdown(wait=True)

    assert len(sent_envelopes) == 1
    assert sent_envelopes[0]["msg_type"] == "interactive"
    assert "timestamp" in sent_envelopes[0]
    assert "sign" in sent_envelopes[0]


def test_violation_escalation_triggers_notification_and_bypasses_warning_cooldown() -> None:
    for min_severity, expected_count in (("WARNING", 2), ("CRITICAL", 1)):
        db = Database("sqlite+pysqlite:///:memory:")
        db.create_schema()
        sent_envelopes: list[dict[str, Any]] = []
        notifier = FeishuNotificationService(
            "https://open.feishu.cn/open-apis/bot/v2/hook/mock-token",
            enabled=True,
            cooldown_seconds=60,
            min_severity=min_severity,
            transport=CallableWebhookTransport(
                lambda url, payload, timeout, box=sent_envelopes: box.append(payload) or {"code": 0}
            ),
        )
        perception = PerceptionService(db, notification_service=notifier)
        event_uuid = uuid4()
        base_time = datetime(2026, 11, 3, 2, 30, 0, tzinfo=timezone.utc)
        try:
            # 1. Initial WARNING event
            perception.upsert_event(
                SafetyViolationEventV1(
                    event_uuid=event_uuid,
                    camera_id="cam-zone-1",
                    monitor_session_id="sess-1",
                    track_id=9,
                    violation_type="DANGER_ZONE_INTRUSION",
                    severity="WARNING",
                    status="ACTIVE",
                    zone_id="z-1",
                    zone_name="吊装危险区",
                    occurred_at_utc=base_time,
                    duration_seconds=0.0,
                )
            )
            # 2. Routine heartbeat update at same WARNING severity -> must NOT duplicate alert
            perception.upsert_event(
                SafetyViolationEventV1(
                    event_uuid=event_uuid,
                    camera_id="cam-zone-1",
                    monitor_session_id="sess-1",
                    track_id=9,
                    violation_type="DANGER_ZONE_INTRUSION",
                    severity="WARNING",
                    status="ACTIVE",
                    zone_id="z-1",
                    zone_name="吊装危险区",
                    occurred_at_utc=base_time,
                    duration_seconds=2.5,
                )
            )
            # 3. Escalation to CRITICAL -> MUST notify and penetrate WARNING cooldown
            perception.upsert_event(
                SafetyViolationEventV1(
                    event_uuid=event_uuid,
                    camera_id="cam-zone-1",
                    monitor_session_id="sess-1",
                    track_id=9,
                    violation_type="DANGER_ZONE_INTRUSION",
                    severity="CRITICAL",
                    status="ACTIVE",
                    zone_id="z-1",
                    zone_name="吊装危险区",
                    occurred_at_utc=base_time,
                    duration_seconds=5.2,
                )
            )
            notifier.flush(timeout=5.0)
        finally:
            notifier.shutdown(wait=True)

        assert len(sent_envelopes) == expected_count
        assert "风险升级" in sent_envelopes[-1]["card"]["header"]["title"]["content"]


def test_composite_notification_service_broadcasts_and_isolates_failures() -> None:
    class FailingChannel(BaseNotificationChannel):
        channel_name = "failing"

        def send_custom_briefing(self, title: str, summary_markdown: str, *, sync: bool = False):
            raise RuntimeError("boom")

    class HealthyChannel(BaseNotificationChannel):
        channel_name = "healthy"

        def __init__(self) -> None:
            self.received: list[str] = []

        def send_custom_briefing(self, title: str, summary_markdown: str, *, sync: bool = False):
            self.received.append(title)
            return {"ok": True, "channel": self.channel_name}

    healthy = HealthyChannel()
    composite = CompositeNotificationService([FailingChannel(), healthy])
    res = composite.send_custom_briefing("测试", "内容", sync=True)
    assert res["ok"] is True
    assert healthy.received == ["测试"]
    assert len(res["channels"]) == 2


def test_stream_consumer_acks_only_on_non_retryable_or_success() -> None:
    fake_client = fakeredis.FakeRedis(decode_responses=True)
    stream = RedisEventStreamAdapter(
        fake_client,
        KeyBuilder(prefix="test_notify"),
        stream_name="violation_events",
        consumer_group="workers",
    )
    fake_client.xgroup_create(stream.stream_key, stream.consumer_group, id="0", mkstream=True)

    attempts = 0

    def flaky_transport(_url: str, _payload: dict[str, Any], _timeout: float) -> dict[str, Any]:
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise httpx.ConnectTimeout("temporary timeout")
        return {"code": 0}

    notifier = FeishuNotificationService(
        "https://open.feishu.cn/open-apis/bot/v2/hook/mock-token",
        enabled=True,
        transport=CallableWebhookTransport(flaky_transport),
    )

    def handle_payload(payload: dict[str, Any]) -> None:
        record = ViolationRecord.model_validate(payload["record"])
        escalated = bool(payload.get("escalated", False))
        res = notifier.notify_violation_event(record, bypass_throttle=escalated, escalated=escalated, sync=True)
        if isinstance(res, dict) and not res.get("ok") and not res.get("skipped") and res.get("retryable"):
            raise RuntimeError(res.get("error") or "retryable error")

    try:
        record = _make_violation_record()
        stream.publish_event({"event_type": "violation_event", "escalated": False, "record": record.model_dump(mode="json")})
        entries = fake_client.xreadgroup(
            groupname=stream.consumer_group,
            consumername=stream.consumer_id,
            streams={stream.stream_key: ">"},
            count=1,
        )
        msg_id, fields = entries[0][1][0]
        # First delivery fails with transient timeout -> must NOT ACK
        assert stream._process_stream_message(str(msg_id), fields, handle_payload) is False
        # Reclaim succeeds once transport recovers
        notifier.policy.throttle.reset()
        assert stream.reclaim_pending_messages(handle_payload, min_idle_ms=0) == 1
        assert attempts == 2
    finally:
        notifier.shutdown(wait=True)


def test_rectification_rollback_does_not_dispatch_notification() -> None:
    db = Database("sqlite+pysqlite:///:memory:")
    db.create_schema()
    sent_envelopes: list[dict[str, Any]] = []
    notifier = FeishuNotificationService(
        "https://open.feishu.cn/open-apis/bot/v2/hook/mock-token",
        enabled=True,
        transport=CallableWebhookTransport(
            lambda url, payload, timeout: sent_envelopes.append(payload) or {"code": 0}
        ),
    )
    service = AgentWriteActionService(db, camera_management=None, notification_service=notifier)
    try:
        # Attempting to execute a non-existent task fails cleanly before/without dispatching notification
        from agent.contracts.chat import ToolDecision
        from agent.services.agent_write_actions import AgentWriteActionError

        with pytest.raises(AgentWriteActionError):
            service.execute_direct(
                "conv-rollback",
                ToolDecision(
                    tool_name="create_rectification_task",
                    violation_event_uuid=str(uuid4()),
                    task_title="未命中事件",
                    task_owner="李工",
                    task_due_at_utc=datetime.now(timezone.utc) + timedelta(hours=2),
                    purpose="测试失败回滚不发通知",
                ),
            )
        notifier.flush(timeout=5.0)
    finally:
        notifier.shutdown(wait=True)
    assert sent_envelopes == []


def test_settings_validation_and_intent_pruning_for_feishu() -> None:
    bad_settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        internal_perception_token="tok",
        llm_provider="fake",
        auto_create_schema=True,
        feishu_alert_min_severity="INVALID_LEVEL",
    )
    with pytest.raises(RuntimeError, match="FEISHU_ALERT_MIN_SEVERITY"):
        bad_settings.validate_for_runtime()

    db = Database("sqlite+pysqlite:///:memory:")
    db.create_schema()
    notifier = FeishuNotificationService(
        "https://open.feishu.cn/open-apis/bot/v2/hook/mock-token",
        enabled=True,
    )
    try:
        with db.session() as session:
            ctx = ToolContext(
                repository=ViolationRepository(session),
                notification_service=notifier,
            )
            catalog = DEFAULT_TOOL_CATALOG.available_catalog(
                ctx,
                question="请给飞书群发送一条安全通报简报",
                prune_by_intent=True,
            )
            assert any(item["name"] == "send_feishu_notification" for item in catalog)
    finally:
        notifier.shutdown(wait=True)


def test_full_business_lifecycle_feishu_notifications(tmp_path) -> None:
    sent_envelopes: list[dict[str, Any]] = []
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        internal_perception_token="contract-test-token",
        llm_provider="fake",
        auto_create_schema=True,
        app_base_path="/helmet",
        learning_report_directory=str(tmp_path / "reports"),
        learning_public_base_url="http://47.95.234.149/helmet",
        feishu_notify_enabled=True,
        feishu_webhook_url="https://open.feishu.cn/open-apis/bot/v2/hook/mock-hook",
        feishu_web_base_url="http://47.95.234.149/helmet",
        feishu_alert_cooldown_seconds=60,
        feishu_alert_min_severity="WARNING",
        feishu_test_default_title="自定义配置飞书测试标题",
    )
    app = create_app(settings)
    app.state.notification_service.set_transport(
        CallableWebhookTransport(
            lambda url, payload, timeout: sent_envelopes.append(payload) or {"code": 0, "msg": "success"}
        )
    )

    internal_headers = {"Authorization": "Bearer contract-test-token"}
    with TestClient(app) as client:
        # 1. Perception violation CREATED -> triggers violation alert card
        event_uuid = str(uuid4())
        event_resp = client.post(
            "/internal/v1/perception/events",
            headers=internal_headers,
            json={
                "schema_version": "1.0",
                "event_uuid": event_uuid,
                "event_action": "UPSERT",
                "camera_id": "camera-a01",
                "monitor_session_id": "session-a01",
                "track_id": 7,
                "violation_type": "DANGER_ZONE_INTRUSION",
                "severity": "CRITICAL",
                "status": "ACTIVE",
                "zone_id": "zone-crane",
                "zone_name": "塔吊回转半径区",
                "occurred_at_utc": "2026-11-03T02:30:00Z",
                "resolved_at_utc": None,
                "duration_seconds": 0,
                "snapshot_uri": "snapshots/20261103/ev1.jpg",
                "model_name": "yolov8s",
                "model_version": "2026.11",
                "extra_details": {},
            },
        )
        assert event_resp.status_code == 200

        # 2. Propose & confirm rectification creation -> triggers rectification created card
        conversation_id = "feishu-e2e-conv"
        propose_create = client.post(
            "/api/v1/rectification-tasks/pending-create",
            json={
                "conversation_id": conversation_id,
                "event_uuid": event_uuid,
                "title": "清退塔吊回转区人员",
                "description": "立即清退危险区人员并拉设警戒带",
                "owner": "张班长",
                "due_at_utc": "2026-11-04T10:00:00Z",
            },
        )
        assert propose_create.status_code == 200
        create_conf_id = propose_create.json()["pending_action"]["confirmation_id"]

        confirm_create = client.post(
            f"/api/v1/agent/actions/{create_conf_id}/confirm",
            json={"conversation_id": conversation_id},
        )
        assert confirm_create.status_code == 200
        task_id = confirm_create.json()["result"]["task_id"]

        # 3. Propose & confirm rectification completion -> triggers rectification completed card
        propose_complete = client.post(
            f"/api/v1/rectification-tasks/{task_id}/pending-update",
            json={
                "conversation_id": conversation_id,
                "status": "COMPLETED",
                "note": "已完成现场警戒线加固，人员已撤离",
            },
        )
        assert propose_complete.status_code == 200
        complete_conf_id = propose_complete.json()["pending_action"]["confirmation_id"]

        confirm_complete = client.post(
            f"/api/v1/agent/actions/{complete_conf_id}/confirm",
            json={"conversation_id": conversation_id},
        )
        assert confirm_complete.status_code == 200

        # 4. Generate & confirm safety report -> triggers report confirmed card without /helmet/helmet
        now = datetime.now(timezone.utc)
        gen_report = client.post(
            "/api/v1/learning/reports",
            json={
                "period_start_utc": (now.replace(hour=0, minute=0, second=0)).isoformat(),
                "period_end_utc": now.isoformat(),
            },
        )
        assert gen_report.status_code == 201
        report_id = gen_report.json()["report_id"]

        confirm_report = client.post(f"/api/v1/learning/reports/{report_id}:confirm")
        assert confirm_report.status_code == 200

        # 5. Generate & publish worker training -> triggers training published card
        gen_training = client.post(
            "/api/v1/learning/training",
            json={
                "report_id": report_id,
                "title": "塔吊交叉作业安全培训",
                "target_count": 20,
                "pass_score": 80,
                "question_count": 3,
            },
        )
        assert gen_training.status_code == 201
        training_id = gen_training.json()["task_id"]

        pub_training = client.post(f"/api/v1/learning/training/{training_id}:publish")
        assert pub_training.status_code == 200

        # 6. Synchronous test endpoint with empty payload -> uses configured Settings default title
        test_api = client.post("/api/v1/safety/notifications/feishu/test", json={})
        assert test_api.status_code == 200
        assert test_api.json()["status"] == "sent"

        app.state.notification_service.flush(timeout=5.0)

    assert len(sent_envelopes) == 6
    titles = [env["card"]["header"]["title"]["content"] for env in sent_envelopes]
    assert any("施工安全告警" in t for t in titles)
    assert any("整改督办" in t for t in titles)
    assert any("隐患销项" in t for t in titles)
    assert any("安全周报" in t for t in titles)
    assert any("全员安全教育" in t for t in titles)
    assert any("自定义配置飞书测试标题" in t for t in titles)

    # Verify bug fixes end-to-end
    violation_env = next(e for e in sent_envelopes if "施工安全告警" in e["card"]["header"]["title"]["content"])
    assert "2026-11-03 10:30:00" in violation_env["card"]["elements"][0]["fields"][4]["text"]["content"]

    report_env = next(e for e in sent_envelopes if "安全周报" in e["card"]["header"]["title"]["content"])
    pdf_url = report_env["card"]["elements"][3]["actions"][0]["url"]
    assert pdf_url == f"http://47.95.234.149/helmet/api/v1/learning/reports/{report_id}/pdf"
