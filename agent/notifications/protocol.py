"""Notification port abstraction, multi-channel composite dispatcher, and provider registry."""
from __future__ import annotations

from collections.abc import Callable, Sequence
from concurrent.futures import Future
from typing import TYPE_CHECKING, Any, Protocol, runtime_checkable

from agent.contracts.learning import ReportResponse, TrainingResponse
from agent.contracts.query import ViolationRecord
from .feishu_service import FeishuNotificationService

if TYPE_CHECKING:
    from agent.core.config import Settings


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


class BaseNotificationChannel:
    """Default base implementation allowing channels to selectively implement only needed methods (ISP)."""

    @property
    def is_configured(self) -> bool:
        return True

    def notify_violation_event(
        self,
        record: ViolationRecord,
        *,
        bypass_throttle: bool = False,
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

    def shutdown(self, wait: bool = False) -> None:
        pass


class CompositeNotificationService:
    """Broadcasts notifications across multiple registered NotificationPort channels."""

    def __init__(self, channels: Sequence[NotificationPort]) -> None:
        self.channels: list[NotificationPort] = list(channels)

    @property
    def is_configured(self) -> bool:
        return any(ch.is_configured for ch in self.channels)

    def add_channel(self, channel: NotificationPort) -> None:
        self.channels.append(channel)

    def notify_violation_event(
        self,
        record: ViolationRecord,
        *,
        bypass_throttle: bool = False,
        sync: bool = False,
    ) -> dict[str, Any] | Future[dict[str, Any]] | None:
        result = None
        for ch in self.channels:
            if ch.is_configured:
                res = ch.notify_violation_event(record, bypass_throttle=bypass_throttle, sync=sync)
                if result is None:
                    result = res
        return result

    def notify_rectification_created(
        self,
        task_payload: dict[str, Any],
        *,
        sync: bool = False,
    ) -> dict[str, Any] | Future[dict[str, Any]] | None:
        result = None
        for ch in self.channels:
            if ch.is_configured:
                res = ch.notify_rectification_created(task_payload, sync=sync)
                if result is None:
                    result = res
        return result

    def notify_rectification_completed(
        self,
        task_payload: dict[str, Any],
        *,
        sync: bool = False,
    ) -> dict[str, Any] | Future[dict[str, Any]] | None:
        result = None
        for ch in self.channels:
            if ch.is_configured:
                res = ch.notify_rectification_completed(task_payload, sync=sync)
                if result is None:
                    result = res
        return result

    def notify_report_confirmed(
        self,
        report: ReportResponse,
        *,
        sync: bool = False,
    ) -> dict[str, Any] | Future[dict[str, Any]] | None:
        result = None
        for ch in self.channels:
            if ch.is_configured:
                res = ch.notify_report_confirmed(report, sync=sync)
                if result is None:
                    result = res
        return result

    def notify_training_published(
        self,
        training: TrainingResponse,
        *,
        sync: bool = False,
    ) -> dict[str, Any] | Future[dict[str, Any]] | None:
        result = None
        for ch in self.channels:
            if ch.is_configured:
                res = ch.notify_training_published(training, sync=sync)
                if result is None:
                    result = res
        return result

    def send_custom_briefing(
        self,
        title: str,
        summary_markdown: str,
        *,
        sync: bool = False,
    ) -> dict[str, Any] | Future[dict[str, Any]] | None:
        results: list[dict[str, Any]] = []
        first_future: Future[dict[str, Any]] | None = None
        for ch in self.channels:
            if ch.is_configured:
                res = ch.send_custom_briefing(title, summary_markdown, sync=sync)
                if isinstance(res, dict):
                    results.append(res)
                elif first_future is None and res is not None:
                    first_future = res
        if sync:
            if not results:
                return {"ok": False, "skipped": True, "reason": "no notification channel configured"}
            return {"ok": any(r.get("ok") for r in results), "channels": results}
        return first_future

    def shutdown(self, wait: bool = False) -> None:
        for ch in self.channels:
            ch.shutdown(wait=wait)


NotificationProviderBuilder = Callable[..., NotificationPort]


def _build_feishu_provider(settings: "Settings", throttle: Any | None = None) -> NotificationPort:
    return FeishuNotificationService(
        settings.feishu_webhook_url,
        webhook_secret=settings.feishu_webhook_secret,
        enabled=settings.feishu_notify_enabled,
        web_base_url=settings.feishu_web_base_url or settings.learning_public_base_url or "http://127.0.0.1:5173",
        timezone_name=settings.learning_timezone,
        cooldown_seconds=settings.feishu_alert_cooldown_seconds,
        min_severity=settings.feishu_alert_min_severity,
        timeout_seconds=settings.feishu_timeout_seconds,
        throttle=throttle,
    )


_NOTIFICATION_PROVIDERS: dict[str, NotificationProviderBuilder] = {
    "feishu": _build_feishu_provider,
}


def register_notification_provider(name: str, builder: NotificationProviderBuilder) -> None:
    """Register an additional notification channel builder (e.g. 'wecom', 'dingtalk', 'webhook')."""
    _NOTIFICATION_PROVIDERS[name.lower()] = builder


def supported_notification_providers() -> frozenset[str]:
    return frozenset(_NOTIFICATION_PROVIDERS)


def create_notification_service(settings: "Settings", throttle: Any | None = None) -> NotificationPort:
    """Build configured notification service(s) from Settings."""
    channels = []
    for builder in _NOTIFICATION_PROVIDERS.values():
        try:
            channels.append(builder(settings, throttle=throttle))
        except TypeError:
            channels.append(builder(settings))
    if len(channels) == 1:
        return channels[0]
    return CompositeNotificationService(channels)
