"""Feishu webhook transport, HMAC-SHA256 signing, and delivery observability (SRP & DIP)."""
from __future__ import annotations

import base64
from collections.abc import Callable
import hashlib
import hmac
import logging
import time
from typing import Any

import httpx

from .protocol import NotificationDeliveryResult, WebhookTransport

logger = logging.getLogger(__name__)


class HttpxWebhookTransport:
    """Default httpx-based JSON webhook transport."""

    def post_json(self, url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        with httpx.Client(timeout=timeout) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            return response.json()


class CallableWebhookTransport:
    """Adapter wrapping a plain callable into WebhookTransport."""

    def __init__(self, sender: Callable[[str, dict[str, Any], float], dict[str, Any]]) -> None:
        self._sender = sender

    def post_json(self, url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        return self._sender(url, payload, timeout)


def _mask_webhook_url(url: str) -> str:
    stripped = url.strip()
    if "/" not in stripped:
        return "***"
    prefix, _, tail = stripped.rpartition("/")
    if len(tail) <= 6:
        return f"{prefix}/***"
    return f"{prefix}/{tail[:4]}...{tail[-4:]}"


def _extract_card_title(card: dict[str, Any]) -> str:
    header = card.get("header")
    if isinstance(header, dict):
        title = header.get("title")
        if isinstance(title, dict):
            content = title.get("content")
            if isinstance(content, str):
                return content
    return "interactive-card"


def _is_retryable_exception(exc: Exception) -> bool:
    if isinstance(exc, (httpx.TimeoutException, httpx.TransportError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status == 429 or status >= 500
    return True


class FeishuWebhookClient:
    """Handles Feishu custom bot message signing, HTTP delivery, and structured logging."""

    channel_name: str = "feishu"

    def __init__(
        self,
        webhook_url: str,
        *,
        webhook_secret: str = "",
        enabled: bool = True,
        timeout_seconds: float = 5.0,
        transport: WebhookTransport | None = None,
    ) -> None:
        self.webhook_url = webhook_url.strip()
        self.webhook_secret = webhook_secret.strip()
        self.enabled = bool(enabled and self.webhook_url)
        self.timeout_seconds = max(0.5, float(timeout_seconds))
        self.transport: WebhookTransport = transport or HttpxWebhookTransport()

    @property
    def is_configured(self) -> bool:
        return self.enabled and bool(self.webhook_url)

    @staticmethod
    def compute_signature(timestamp: str, secret: str) -> str:
        """Compute Feishu custom bot HMAC-SHA256 base64 signature."""
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

    def send_card(self, card: dict[str, Any]) -> NotificationDeliveryResult:
        """Send an interactive card synchronously and return structured delivery status."""
        if not self.is_configured:
            return NotificationDeliveryResult(
                ok=False,
                skipped=True,
                channel=self.channel_name,
                reason="feishu webhook not configured or disabled",
            )

        card_title = _extract_card_title(card)
        masked_target = _mask_webhook_url(self.webhook_url)
        envelope = self.build_envelope(card)
        try:
            data = self.transport.post_json(self.webhook_url, envelope, self.timeout_seconds)
            code = data.get("code", data.get("StatusCode", -1))
            if code != 0:
                logger.warning(
                    "Feishu webhook returned non-zero code (target=%s, title=%s, response=%s)",
                    masked_target,
                    card_title,
                    data,
                )
                return NotificationDeliveryResult(
                    ok=False,
                    channel=self.channel_name,
                    retryable=False,
                    response=data,
                )
            logger.info(
                "Feishu notification delivered (target=%s, title=%s)",
                masked_target,
                card_title,
            )
            return NotificationDeliveryResult(
                ok=True,
                channel=self.channel_name,
                response=data,
            )
        except Exception as exc:
            retryable = _is_retryable_exception(exc)
            logger.warning(
                "Feishu webhook delivery failed (target=%s, title=%s, retryable=%s): %s",
                masked_target,
                card_title,
                retryable,
                exc,
            )
            return NotificationDeliveryResult(
                ok=False,
                channel=self.channel_name,
                error=str(exc),
                retryable=retryable,
            )
