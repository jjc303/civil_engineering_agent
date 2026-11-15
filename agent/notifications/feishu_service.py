"""Lightweight Feishu notification orchestrator delegating policy, rendering, and transport (SRP & DIP)."""
from __future__ import annotations

from collections.abc import Callable
from concurrent.futures import Future, ThreadPoolExecutor, wait as wait_futures
import threading
from typing import Any

from agent.contracts.learning import ReportResponse, TrainingResponse
from agent.contracts.query import ViolationRecord
from agent.infra.cache import InMemoryThrottleAdapter
from agent.infra.ports import ThrottlePort
from .feishu_cards import FeishuCardBuilder, FeishuCardConfig
from .feishu_policy import FeishuAlertPolicy
from .feishu_transport import CallableWebhookTransport, FeishuWebhookClient
from .links import DEFAULT_WEB_BASE_URL, NotificationLinkBuilder
from .protocol import BaseNotificationChannel, NotificationDeliveryResult, WebhookTransport

# Backwards-compatible alias referencing the shared ThrottlePort implementation (zero duplication).
AlertThrottle = InMemoryThrottleAdapter


class FeishuNotificationService(BaseNotificationChannel):
    """High-cohesion, non-blocking Feishu custom bot webhook notification channel."""

    channel_name: str = "feishu"

    def __init__(
        self,
        webhook_url: str,
        *,
        webhook_secret: str = "",
        enabled: bool = True,
        web_base_url: str = DEFAULT_WEB_BASE_URL,
        app_base_path: str = "",
        timezone_name: str = "Asia/Shanghai",
        cooldown_seconds: int = 60,
        min_severity: str = "WARNING",
        timeout_seconds: float = 5.0,
        max_workers: int = 2,
        http_sender: Callable[[str, dict[str, Any], float], dict[str, Any]] | None = None,
        transport: WebhookTransport | None = None,
        throttle: ThrottlePort | None = None,
        policy: FeishuAlertPolicy | None = None,
        card_builder: FeishuCardBuilder | None = None,
        card_config: FeishuCardConfig | None = None,
        link_builder: NotificationLinkBuilder | None = None,
    ) -> None:
        resolved_transport = transport or (CallableWebhookTransport(http_sender) if http_sender is not None else None)
        self.client = FeishuWebhookClient(
            webhook_url,
            webhook_secret=webhook_secret,
            enabled=enabled,
            timeout_seconds=timeout_seconds,
            transport=resolved_transport,
        )
        self.policy = policy or FeishuAlertPolicy(
            min_severity=min_severity,
            cooldown_seconds=cooldown_seconds,
            throttle=throttle,
        )
        resolved_links = link_builder or NotificationLinkBuilder(
            web_base_url,
            app_base_path=app_base_path,
        )
        resolved_config = card_config or FeishuCardConfig(timezone_name=timezone_name)
        self.card_builder = card_builder or FeishuCardBuilder(
            link_builder=resolved_links,
            config=resolved_config,
        )
        self.throttle = self.policy.throttle
        self.web_base_url = resolved_links.base_url
        self.timezone_name = resolved_config.timezone_name
        self._executor = ThreadPoolExecutor(max_workers=max(1, max_workers), thread_name_prefix="feishu-webhook")
        self._pending_lock = threading.Lock()
        self._pending_futures: set[Future[dict[str, Any]]] = set()
        self._closed = False

    @property
    def is_configured(self) -> bool:
        return self.client.is_configured

    @staticmethod
    def compute_signature(timestamp: str, secret: str) -> str:
        return FeishuWebhookClient.compute_signature(timestamp, secret)

    def build_envelope(self, card: dict[str, Any]) -> dict[str, Any]:
        return self.client.build_envelope(card)

    def set_transport(self, transport: WebhookTransport) -> None:
        """Replace underlying webhook transport (DIP helper for tests or custom adapters)."""
        self.client.transport = transport

    def send_card_sync(self, card: dict[str, Any]) -> dict[str, Any]:
        """Synchronously send a card to Feishu webhook and return status dict."""
        return self.client.send_card(card).to_dict()

    def dispatch_card_async(self, card: dict[str, Any]) -> Future[dict[str, Any]] | None:
        """Submit card delivery to the background thread pool without blocking caller."""
        if not self.is_configured or self._closed:
            return None
        try:
            future = self._executor.submit(self.send_card_sync, card)
        except RuntimeError:
            return None

        with self._pending_lock:
            self._pending_futures.add(future)

        def _discard(done_future: Future[dict[str, Any]]) -> None:
            with self._pending_lock:
                self._pending_futures.discard(done_future)

        future.add_done_callback(_discard)
        return future

    def _dispatch(self, card: dict[str, Any], *, sync: bool) -> dict[str, Any] | Future[dict[str, Any]] | None:
        return self.send_card_sync(card) if sync else self.dispatch_card_async(card)

    def notify_violation_event(
        self,
        record: ViolationRecord,
        *,
        bypass_throttle: bool = False,
        escalated: bool = False,
        sync: bool = False,
    ) -> dict[str, Any] | Future[dict[str, Any]] | None:
        """Trigger real-time safety violation alert card if eligibility policy passes."""
        if not self.is_configured:
            if sync:
                return NotificationDeliveryResult(
                    ok=False,
                    skipped=True,
                    channel=self.channel_name,
                    reason="feishu webhook not configured or disabled",
                ).to_dict()
            return None

        allowed, skip_reason = self.policy.evaluate(
            record,
            bypass_throttle=bypass_throttle,
            escalated=escalated,
        )
        if not allowed:
            if sync:
                return NotificationDeliveryResult(
                    ok=False,
                    skipped=True,
                    channel=self.channel_name,
                    reason=skip_reason,
                ).to_dict()
            return None

        card = self.card_builder.violation_alert(record, escalated=escalated)
        return self._dispatch(card, sync=sync)

    def notify_rectification_created(
        self,
        task_payload: dict[str, Any],
        *,
        sync: bool = False,
    ) -> dict[str, Any] | Future[dict[str, Any]] | None:
        if not self.is_configured:
            return None
        return self._dispatch(self.card_builder.rectification_created(task_payload), sync=sync)

    def notify_rectification_completed(
        self,
        task_payload: dict[str, Any],
        *,
        sync: bool = False,
    ) -> dict[str, Any] | Future[dict[str, Any]] | None:
        if not self.is_configured:
            return None
        return self._dispatch(self.card_builder.rectification_completed(task_payload), sync=sync)

    def notify_report_confirmed(
        self,
        report: ReportResponse,
        *,
        sync: bool = False,
    ) -> dict[str, Any] | Future[dict[str, Any]] | None:
        if not self.is_configured:
            return None
        return self._dispatch(self.card_builder.report_confirmed(report), sync=sync)

    def notify_training_published(
        self,
        training: TrainingResponse,
        *,
        sync: bool = False,
    ) -> dict[str, Any] | Future[dict[str, Any]] | None:
        if not self.is_configured:
            return None
        return self._dispatch(self.card_builder.training_published(training), sync=sync)

    def send_custom_briefing(
        self,
        title: str,
        summary_markdown: str,
        *,
        sync: bool = False,
    ) -> dict[str, Any] | Future[dict[str, Any]] | None:
        if not self.is_configured:
            return (
                NotificationDeliveryResult(
                    ok=False,
                    skipped=True,
                    channel=self.channel_name,
                    reason="feishu webhook not configured",
                ).to_dict()
                if sync
                else None
            )
        return self._dispatch(self.card_builder.custom_briefing(title, summary_markdown), sync=sync)

    def flush(self, timeout: float | None = None) -> None:
        """Wait for currently queued async notification tasks to settle."""
        with self._pending_lock:
            pending = list(self._pending_futures)
        if pending:
            wait_futures(pending, timeout=timeout)

    def shutdown(self, wait: bool = False) -> None:
        self._closed = True
        self._executor.shutdown(wait=wait, cancel_futures=not wait)
