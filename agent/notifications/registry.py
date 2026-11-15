"""Notification provider registry and Settings-driven factory assembly (OCP & DIP)."""
from __future__ import annotations

from typing import TYPE_CHECKING

from agent.infra.ports import ThrottlePort
from .feishu_cards import FeishuCardConfig
from .feishu_service import FeishuNotificationService
from .links import DEFAULT_WEB_BASE_URL, NotificationLinkBuilder
from .protocol import (
    CompositeNotificationService,
    NotificationPort,
    NotificationProviderBuilder,
)

if TYPE_CHECKING:
    from agent.core.config import Settings


def _build_feishu_provider(
    settings: "Settings",
    throttle: ThrottlePort | None = None,
) -> NotificationPort:
    web_base = settings.feishu_web_base_url or settings.learning_public_base_url or DEFAULT_WEB_BASE_URL
    link_builder = NotificationLinkBuilder(
        web_base,
        app_base_path=settings.app_base_path,
        routes=settings.feishu_routes(),
    )
    card_config = FeishuCardConfig(
        brand_name=settings.feishu_brand_name,
        timezone_name=settings.learning_timezone,
        summary_max_chars=settings.feishu_summary_max_chars,
        remediation_max_chars=settings.feishu_remediation_max_chars,
        material_preview_max_chars=settings.feishu_material_preview_max_chars,
        standard_hint_overrides=settings.parsed_feishu_standard_hints(),
    )
    return FeishuNotificationService(
        settings.feishu_webhook_url,
        webhook_secret=settings.feishu_webhook_secret,
        enabled=settings.feishu_notify_enabled,
        web_base_url=web_base,
        app_base_path=settings.app_base_path,
        timezone_name=settings.learning_timezone,
        cooldown_seconds=settings.feishu_alert_cooldown_seconds,
        min_severity=settings.feishu_alert_min_severity,
        timeout_seconds=settings.feishu_timeout_seconds,
        max_workers=settings.feishu_max_workers,
        throttle=throttle,
        link_builder=link_builder,
        card_config=card_config,
    )


_NOTIFICATION_PROVIDERS: dict[str, NotificationProviderBuilder] = {
    "feishu": _build_feishu_provider,
}


def register_notification_provider(name: str, builder: NotificationProviderBuilder) -> None:
    """Register an additional notification channel builder (e.g. 'wecom', 'dingtalk', 'webhook')."""
    _NOTIFICATION_PROVIDERS[name.lower()] = builder


def supported_notification_providers() -> frozenset[str]:
    return frozenset(_NOTIFICATION_PROVIDERS)


def create_notification_service(
    settings: "Settings",
    throttle: ThrottlePort | None = None,
) -> NotificationPort:
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
