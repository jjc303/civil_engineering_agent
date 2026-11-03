from __future__ import annotations

import base64
from concurrent.futures import Future, ThreadPoolExecutor
import hashlib
import hmac
import logging
import threading
import time
from typing import Any, Callable

import httpx

from agent.contracts.learning import ReportResponse, TrainingResponse
from agent.contracts.query import ViolationRecord
from .feishu_cards import FeishuCardBuilder

logger = logging.getLogger(__name__)

SEVERITY_RANK: dict[str, int] = {
    "INFO": 1,
    "WARNING": 2,
    "CRITICAL": 3,
}


class AlertThrottle:
    """Thread-safe sliding window throttle to prevent duplicate alert flooding."""

    def __init__(self, cooldown_seconds: int = 60) -> None:
        self.cooldown_seconds = max(0, cooldown_seconds)
        self._lock = threading.Lock()
        self._last_sent: dict[tuple[str, str, str], float] = {}

    def should_send(self, camera_id: str, violation_type: str, zone_id: str | None = None) -> bool:
        if self.cooldown_seconds <= 0:
            return True
        key = (camera_id, violation_type, zone_id or "")
        now = time.monotonic()
        with self._lock:
            last = self._last_sent.get(key)
            if last is not None and (now - last) < self.cooldown_seconds:
                return False
            self._last_sent[key] = now
            # Prevent unbounded dict growth in long-running processes
            if len(self._last_sent) > 2048:
                cutoff = now - self.cooldown_seconds
                self._last_sent = {k: v for k, v in self._last_sent.items() if v >= cutoff}
            return True

    def reset(self) -> None:
        with self._lock:
            self._last_sent.clear()


class FeishuNotificationService:
    """High-cohesion, non-blocking Feishu custom bot webhook notification service."""

    def __init__(
        self,
        webhook_url: str,
        *,
        webhook_secret: str = "",
        enabled: bool = True,
        web_base_url: str = "http://127.0.0.1:5173",
        timezone_name: str = "Asia/Shanghai",
        cooldown_seconds: int = 60,
        min_severity: str = "WARNING",
        timeout_seconds: float = 5.0,
        max_workers: int = 2,
        http_sender: Callable[[str, dict[str, Any], float], dict[str, Any]] | None = None,
    ) -> None:
        self.webhook_url = webhook_url.strip()
        self.webhook_secret = webhook_secret.strip()
        self.enabled = bool(enabled and self.webhook_url)
        self.web_base_url = web_base_url.rstrip("/") or "http://127.0.0.1:5173"
        self.timezone_name = timezone_name
        self.min_severity_rank = SEVERITY_RANK.get(min_severity.upper(), 2)
        self.timeout_seconds = max(1.0, timeout_seconds)
        self.throttle = AlertThrottle(cooldown_seconds=cooldown_seconds)
        self._http_sender = http_sender or self._default_http_post
        self._executor = ThreadPoolExecutor(max_workers=max_workers, thread_name_prefix="feishu-webhook")
        self._closed = False

    @property
    def is_configured(self) -> bool:
        return self.enabled and bool(self.webhook_url)

    @staticmethod
    def compute_signature(timestamp: str, secret: str) -> str:
        string_to_sign = f"{timestamp}\n{secret}"
        hmac_code = hmac.new(string_to_sign.encode("utf-8"), digestmod=hashlib.sha256).digest()
        return base64.b64encode(hmac_code).decode("utf-8")

    def build_envelope(self, card: dict[str, Any]) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "msg_type": "interactive",
            "card": card,
        }
        if self.webhook_secret:
            ts = str(int(time.time()))
            payload["timestamp"] = ts
            payload["sign"] = self.compute_signature(ts, self.webhook_secret)
        return payload

    @staticmethod
    def _default_http_post(url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            return response.json()

    def send_card_sync(self, card: dict[str, Any]) -> dict[str, Any]:
        """Synchronously send a card to Feishu webhook and return status dict."""
        if not self.is_configured:
            return {"ok": False, "skipped": True, "reason": "feishu webhook not configured or disabled"}
        envelope = self.build_envelope(card)
        try:
            data = self._http_sender(self.webhook_url, envelope, self.timeout_seconds)
            code = data.get("code", data.get("StatusCode", -1))
            if code != 0:
                logger.warning("Feishu webhook returned non-zero code: %s", data)
                return {"ok": False, "response": data}
            return {"ok": True, "response": data}
        except Exception as exc:
            logger.warning("Feishu webhook delivery failed: %s", exc)
            return {"ok": False, "error": str(exc)}

    def dispatch_card_async(self, card: dict[str, Any]) -> Future[dict[str, Any]] | None:
        """Submit card delivery to the background thread pool without blocking caller."""
        if not self.is_configured or self._closed:
            return None
        try:
            return self._executor.submit(self.send_card_sync, card)
        except RuntimeError:
            # Executor already shut down
            return None

    def notify_violation_event(
        self,
        record: ViolationRecord,
        *,
        bypass_throttle: bool = False,
        sync: bool = False,
    ) -> dict[str, Any] | Future[dict[str, Any]] | None:
        """Trigger real-time safety violation alert card if severity and cooldown qualify."""
        if not self.is_configured:
            return None
        if record.status != "ACTIVE":
            return None
        event_rank = SEVERITY_RANK.get(record.severity.upper(), 1)
        if event_rank < self.min_severity_rank:
            return None
        if not bypass_throttle and not self.throttle.should_send(record.camera_id, record.violation_type, record.zone_id):
            logger.debug(
                "Skipped throttled Feishu violation alert for camera=%s type=%s",
                record.camera_id,
                record.violation_type,
            )
            return None

        card = FeishuCardBuilder.build_violation_alert_card(
            record,
            web_base_url=self.web_base_url,
            timezone_name=self.timezone_name,
        )
        return self.send_card_sync(card) if sync else self.dispatch_card_async(card)

    def notify_rectification_created(
        self,
        task_payload: dict[str, Any],
        *,
        sync: bool = False,
    ) -> dict[str, Any] | Future[dict[str, Any]] | None:
        """Trigger rectification task assignment card."""
        if not self.is_configured:
            return None
        card = FeishuCardBuilder.build_rectification_created_card(
            task_payload,
            web_base_url=self.web_base_url,
            timezone_name=self.timezone_name,
        )
        return self.send_card_sync(card) if sync else self.dispatch_card_async(card)

    def notify_rectification_completed(
        self,
        task_payload: dict[str, Any],
        *,
        sync: bool = False,
    ) -> dict[str, Any] | Future[dict[str, Any]] | None:
        """Trigger rectification task completion & resolution card."""
        if not self.is_configured:
            return None
        card = FeishuCardBuilder.build_rectification_completed_card(
            task_payload,
            web_base_url=self.web_base_url,
            timezone_name=self.timezone_name,
        )
        return self.send_card_sync(card) if sync else self.dispatch_card_async(card)

    def notify_report_confirmed(
        self,
        report: ReportResponse,
        *,
        sync: bool = False,
    ) -> dict[str, Any] | Future[dict[str, Any]] | None:
        """Trigger safety report confirmation & PDF ready card."""
        if not self.is_configured:
            return None
        card = FeishuCardBuilder.build_report_confirmed_card(
            report,
            web_base_url=self.web_base_url,
            timezone_name=self.timezone_name,
        )
        return self.send_card_sync(card) if sync else self.dispatch_card_async(card)

    def notify_training_published(
        self,
        training: TrainingResponse,
        *,
        sync: bool = False,
    ) -> dict[str, Any] | Future[dict[str, Any]] | None:
        """Trigger worker training task publication card with H5 link."""
        if not self.is_configured:
            return None
        card = FeishuCardBuilder.build_training_published_card(
            training,
            web_base_url=self.web_base_url,
            timezone_name=self.timezone_name,
        )
        return self.send_card_sync(card) if sync else self.dispatch_card_async(card)

    def send_custom_briefing(
        self,
        title: str,
        summary_markdown: str,
        *,
        sync: bool = False,
    ) -> dict[str, Any] | Future[dict[str, Any]] | None:
        """Send an AI safety briefing or test card."""
        if not self.is_configured:
            return {"ok": False, "skipped": True, "reason": "feishu webhook not configured"} if sync else None
        card = FeishuCardBuilder.build_custom_briefing_card(
            title=title,
            summary_markdown=summary_markdown,
            web_base_url=self.web_base_url,
            timezone_name=self.timezone_name,
        )
        return self.send_card_sync(card) if sync else self.dispatch_card_async(card)

    def shutdown(self, wait: bool = False) -> None:
        self._closed = True
        self._executor.shutdown(wait=wait, cancel_futures=not wait)
