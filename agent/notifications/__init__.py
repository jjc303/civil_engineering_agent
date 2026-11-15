from __future__ import annotations

from .feishu_cards import FeishuCardBuilder, FeishuCardConfig, format_local_time
from .feishu_policy import FeishuAlertPolicy
from .feishu_service import AlertThrottle, FeishuNotificationService
from .feishu_transport import CallableWebhookTransport, FeishuWebhookClient, HttpxWebhookTransport
from .links import DEFAULT_NOTIFICATION_ROUTES, NotificationLinkBuilder
from .protocol import (
    BaseNotificationChannel,
    BriefingNotificationPort,
    CompositeNotificationService,
    FlushableNotificationPort,
    LearningNotificationPort,
    NotificationDeliveryResult,
    NotificationPort,
    RectificationNotificationPort,
    ViolationNotificationPort,
    WebhookTransport,
    dispatch_violation_notification,
)
from .registry import (
    create_notification_service,
    register_notification_provider,
    supported_notification_providers,
)

__all__ = [
    "AlertThrottle",
    "BaseNotificationChannel",
    "BriefingNotificationPort",
    "CallableWebhookTransport",
    "CompositeNotificationService",
    "DEFAULT_NOTIFICATION_ROUTES",
    "FeishuAlertPolicy",
    "FeishuCardBuilder",
    "FeishuCardConfig",
    "FeishuNotificationService",
    "FeishuWebhookClient",
    "FlushableNotificationPort",
    "HttpxWebhookTransport",
    "LearningNotificationPort",
    "NotificationDeliveryResult",
    "NotificationLinkBuilder",
    "NotificationPort",
    "RectificationNotificationPort",
    "ViolationNotificationPort",
    "WebhookTransport",
    "create_notification_service",
    "dispatch_violation_notification",
    "format_local_time",
    "register_notification_provider",
    "supported_notification_providers",
]
