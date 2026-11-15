"""Notification port abstractions, delivery result contract, and composite dispatcher (ISP, LSP, DIP)."""
from __future__ import annotations

from collections.abc import Callable, Sequence
from concurrent.futures import Future
from dataclasses import asdict, dataclass
import inspect
import logging
from typing import Any, Protocol, runtime_checkable

from agent.contracts.learning import ReportResponse, TrainingResponse
from agent.contracts.query import ViolationRecord

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class NotificationDeliveryResult:
    """Canonical structured result for notification delivery attempts."""

    ok: bool
    skipped: bool = False
    channel: str = ""
    reason: str = ""
    error: str | None = None
    retryable: bool = False
    response: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        return {k: v for k, v in payload.items() if v is not None and (v != "" or k == "channel")}


@runtime_checkable
class WebhookTransport(Protocol):
    """Transport port for JSON webhook delivery (DIP)."""

    def post_json(self, url: str, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        """Deliver JSON payload to webhook endpoint and return parsed response dict."""
        ...


@runtime_checkable
class ViolationNotificationPort(Protocol):
    """Fine-grained port for violation event notifications (ISP)."""

    @property
    def is_configured(self) -> bool: ...

    def notify_violation_event(
        self,
        record: ViolationRecord,
        *,
        bypass_throttle: bool = False,
        sync: bool = False,
    ) -> dict[str, Any] | Future[dict[str, Any]] | None: ...


@runtime_checkable
class RectificationNotificationPort(Protocol):
    """Fine-grained port for rectification task lifecycle notifications (ISP)."""

    @property
    def is_configured(self) -> bool: ...

    def notify_rectification_created(
        self,
        task_payload: dict[str, Any],
        *,
        sync: bool = False,
    ) -> dict[str, Any] | Future[dict[str, Any]] | None: ...

    def notify_rectification_completed(
        self,
        task_payload: dict[str, Any],
        *,
        sync: bool = False,
    ) -> dict[str, Any] | Future[dict[str, Any]] | None: ...


@runtime_checkable
class LearningNotificationPort(Protocol):
    """Fine-grained port for report and training notifications (ISP)."""

    @property
    def is_configured(self) -> bool: ...

    def notify_report_confirmed(
        self,
        report: ReportResponse,
        *,
        sync: bool = False,
    ) -> dict[str, Any] | Future[dict[str, Any]] | None: ...

    def notify_training_published(
        self,
        training: TrainingResponse,
        *,
        sync: bool = False,
    ) -> dict[str, Any] | Future[dict[str, Any]] | None: ...


@runtime_checkable
class BriefingNotificationPort(Protocol):
    """Fine-grained port for custom markdown briefings (ISP)."""

    @property
    def is_configured(self) -> bool: ...

    def send_custom_briefing(
        self,
        title: str,
        summary_markdown: str,
        *,
        sync: bool = False,
    ) -> dict[str, Any] | Future[dict[str, Any]] | None: ...


@runtime_checkable
class NotificationPort(
    ViolationNotificationPort,
    RectificationNotificationPort,
    LearningNotificationPort,
    BriefingNotificationPort,
    Protocol,
):
    """Composite port interface for safety event, rectification, report, and training notifications."""

    def shutdown(self, wait: bool = False) -> None: ...


@runtime_checkable
class FlushableNotificationPort(Protocol):
    """Optional ISP port for notification channels that buffer async deliveries."""

    def flush(self, timeout: float | None = None) -> None: ...


def _accepts_kwarg(fn: Any, name: str) -> bool:
    try:
        params = inspect.signature(fn).parameters.values()
    except (TypeError, ValueError):
        return False
    return any(p.name == name or p.kind == inspect.Parameter.VAR_KEYWORD for p in params)


def dispatch_violation_notification(
    channel: ViolationNotificationPort,
    record: ViolationRecord,
    *,
    bypass_throttle: bool = False,
    escalated: bool = False,
    sync: bool = False,
) -> dict[str, Any] | Future[dict[str, Any]] | None:
    """Invoke a ViolationNotificationPort while optionally forwarding `escalated` only when supported."""
    if _accepts_kwarg(channel.notify_violation_event, "escalated"):
        return channel.notify_violation_event(  # type: ignore[call-arg]
            record,
            bypass_throttle=bypass_throttle,
            escalated=escalated,
            sync=sync,
        )
    return channel.notify_violation_event(
        record,
        bypass_throttle=bypass_throttle,
        sync=sync,
    )


class BaseNotificationChannel:
    """Default base implementation allowing channels to selectively implement only needed methods (ISP)."""

    channel_name: str = "base"
    channel_label: str = ""
    channel_aliases: tuple[str, ...] = ()

    @property
    def is_configured(self) -> bool:
        return True

    def notify_violation_event(
        self,
        record: ViolationRecord,
        *,
        bypass_throttle: bool = False,
        escalated: bool = False,
        sync: bool = False,
    ) -> dict[str, Any] | Future[dict[str, Any]] | None:
        return None

    def notify_rectification_created(
        self,
        task_payload: dict[str, Any],
        *,
        sync: bool = False,
    ) -> dict[str, Any] | Future[dict[str, Any]] | None:
        return None

    def notify_rectification_completed(
        self,
        task_payload: dict[str, Any],
        *,
        sync: bool = False,
    ) -> dict[str, Any] | Future[dict[str, Any]] | None:
        return None

    def notify_report_confirmed(
        self,
        report: ReportResponse,
        *,
        sync: bool = False,
    ) -> dict[str, Any] | Future[dict[str, Any]] | None:
        return None

    def notify_training_published(
        self,
        training: TrainingResponse,
        *,
        sync: bool = False,
    ) -> dict[str, Any] | Future[dict[str, Any]] | None:
        return None

    def send_custom_briefing(
        self,
        title: str,
        summary_markdown: str,
        *,
        sync: bool = False,
    ) -> dict[str, Any] | Future[dict[str, Any]] | None:
        return None

    def flush(self, timeout: float | None = None) -> None:
        pass

    def shutdown(self, wait: bool = False) -> None:
        pass


class CompositeNotificationService(BaseNotificationChannel):
    """Broadcasts notifications across multiple registered NotificationPort channels with fault isolation."""

    channel_name: str = "composite"

    def __init__(self, channels: Sequence[NotificationPort]) -> None:
        self.channels: list[NotificationPort] = list(channels)

    @property
    def is_configured(self) -> bool:
        return any(ch.is_configured for ch in self.channels)

    def active_channels(self) -> list[NotificationPort]:
        """Return currently configured child channels."""
        return [ch for ch in self.channels if ch.is_configured]

    def active_channel_names(self) -> list[str]:
        """Return normalized channel identifiers for configured child channels."""
        return [
            name
            for ch in self.active_channels()
            if (name := str(getattr(ch, "channel_name", "") or "").strip())
        ]

    def active_channel_labels(self) -> list[str]:
        """Return display labels for configured child channels."""
        labels: list[str] = []
        for ch in self.active_channels():
            label = str(getattr(ch, "channel_label", "") or getattr(ch, "channel_name", "") or "").strip()
            if label and label not in labels:
                labels.append(label)
        return labels

    def active_channel_aliases(self) -> list[str]:
        """Return search/intent aliases declared by configured child channels."""
        aliases: list[str] = []
        for ch in self.active_channels():
            for raw in getattr(ch, "channel_aliases", ()) or ():
                token = str(raw).strip()
                if token and token not in aliases:
                    aliases.append(token)
        return aliases

    def add_channel(self, channel: NotificationPort) -> None:
        self.channels.append(channel)

    def _broadcast(
        self,
        method_name: str,
        *args: Any,
        sync: bool = False,
        **kwargs: Any,
    ) -> dict[str, Any] | Future[dict[str, Any]] | None:
        active_channels = self.active_channels()
        if not active_channels:
            if sync:
                return NotificationDeliveryResult(
                    ok=False,
                    skipped=True,
                    channel=self.channel_name,
                    reason="no notification channel configured",
                ).to_dict()
            return None

        sync_results: list[dict[str, Any]] = []
        first_future: Future[dict[str, Any]] | None = None
        for ch in active_channels:
            try:
                target = getattr(ch, method_name)
                call_kwargs = dict(kwargs)
                if "escalated" in call_kwargs and not _accepts_kwarg(target, "escalated"):
                    call_kwargs.pop("escalated", None)
                res = target(*args, sync=sync, **call_kwargs)
            except Exception as exc:
                logger.warning("Channel %s failed in %s: %s", type(ch).__name__, method_name, exc)
                if sync:
                    sync_results.append(
                        NotificationDeliveryResult(
                            ok=False,
                            channel=getattr(ch, "channel_name", type(ch).__name__),
                            error=str(exc),
                            retryable=True,
                        ).to_dict()
                    )
                continue

            if isinstance(res, dict):
                sync_results.append(res)
            elif first_future is None and isinstance(res, Future):
                first_future = res

        if sync:
            if not sync_results:
                return NotificationDeliveryResult(
                    ok=False,
                    skipped=True,
                    channel=self.channel_name,
                    reason="skipped by channel policy",
                ).to_dict()
            if len(sync_results) == 1:
                return sync_results[0]
            return {
                "ok": any(r.get("ok") for r in sync_results),
                "retryable": any(r.get("retryable") for r in sync_results),
                "channels": sync_results,
            }
        return first_future

    def notify_violation_event(
        self,
        record: ViolationRecord,
        *,
        bypass_throttle: bool = False,
        escalated: bool = False,
        sync: bool = False,
    ) -> dict[str, Any] | Future[dict[str, Any]] | None:
        return self._broadcast(
            "notify_violation_event",
            record,
            bypass_throttle=bypass_throttle,
            escalated=escalated,
            sync=sync,
        )

    def notify_rectification_created(
        self,
        task_payload: dict[str, Any],
        *,
        sync: bool = False,
    ) -> dict[str, Any] | Future[dict[str, Any]] | None:
        return self._broadcast("notify_rectification_created", task_payload, sync=sync)

    def notify_rectification_completed(
        self,
        task_payload: dict[str, Any],
        *,
        sync: bool = False,
    ) -> dict[str, Any] | Future[dict[str, Any]] | None:
        return self._broadcast("notify_rectification_completed", task_payload, sync=sync)

    def notify_report_confirmed(
        self,
        report: ReportResponse,
        *,
        sync: bool = False,
    ) -> dict[str, Any] | Future[dict[str, Any]] | None:
        return self._broadcast("notify_report_confirmed", report, sync=sync)

    def notify_training_published(
        self,
        training: TrainingResponse,
        *,
        sync: bool = False,
    ) -> dict[str, Any] | Future[dict[str, Any]] | None:
        return self._broadcast("notify_training_published", training, sync=sync)

    def send_custom_briefing(
        self,
        title: str,
        summary_markdown: str,
        *,
        sync: bool = False,
    ) -> dict[str, Any] | Future[dict[str, Any]] | None:
        return self._broadcast("send_custom_briefing", title, summary_markdown, sync=sync)

    def flush(self, timeout: float | None = None) -> None:
        for ch in self.channels:
            if isinstance(ch, FlushableNotificationPort):
                ch.flush(timeout=timeout)

    def shutdown(self, wait: bool = False) -> None:
        for ch in self.channels:
            ch.shutdown(wait=wait)


def describe_notification_channels(service: object | None) -> dict[str, Any]:
    """Inspect configured notification channel metadata without hardcoding providers."""
    if service is None or not getattr(service, "is_configured", False):
        return {"configured": False, "channels": [], "labels": [], "aliases": []}

    targets = service.active_channels() if isinstance(service, CompositeNotificationService) else [service]
    channels: list[str] = []
    labels: list[str] = []
    aliases: list[str] = []
    for target in targets:
        ch_name = str(getattr(target, "channel_name", "") or "").strip()
        ch_label = str(getattr(target, "channel_label", "") or "").strip()
        if ch_name and ch_name not in channels:
            channels.append(ch_name)
        effective_label = ch_label or ch_name
        if effective_label and effective_label not in labels:
            labels.append(effective_label)
        for token in (ch_name, ch_label, *(getattr(target, "channel_aliases", ()) or ())):
            cleaned = str(token or "").strip()
            if cleaned and cleaned not in aliases:
                aliases.append(cleaned)
    return {
        "configured": True,
        "channels": channels,
        "labels": labels,
        "aliases": aliases,
    }


NotificationProviderBuilder = Callable[..., NotificationPort]
