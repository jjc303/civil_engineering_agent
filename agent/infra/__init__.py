"""Infrastructure container assembling Cache, Lock, Throttle, and Messaging (SOLID)."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import TYPE_CHECKING

from agent.infra.cache import (
    InMemoryCacheAdapter,
    InMemoryThrottleAdapter,
    RedisCacheAdapter,
    RedisThrottleAdapter,
)
from agent.infra.distributed_lock import (
    InMemoryDistributedLockAdapter,
    RedisDistributedLockAdapter,
)
from agent.infra.messaging import (
    DirectEventStreamAdapter,
    InMemoryBroadcastAdapter,
    RedisEventStreamAdapter,
    RedisPubSubBroadcastAdapter,
)
from agent.infra.ports import (
    CachePort,
    DistributedLockPort,
    EventStreamPort,
    LockHandle,
    RealtimeBroadcastPort,
    ThrottlePort,
)
from agent.infra.redis_client import KeyBuilder, RedisManager

if TYPE_CHECKING:
    from agent.core.config import Settings

logger = logging.getLogger(__name__)

__all__ = [
    "CachePort",
    "DirectEventStreamAdapter",
    "DistributedLockPort",
    "EventStreamPort",
    "InMemoryBroadcastAdapter",
    "InMemoryCacheAdapter",
    "InMemoryDistributedLockAdapter",
    "InMemoryThrottleAdapter",
    "InfraContainer",
    "KeyBuilder",
    "LockHandle",
    "RealtimeBroadcastPort",
    "RedisCacheAdapter",
    "RedisDistributedLockAdapter",
    "RedisEventStreamAdapter",
    "RedisManager",
    "RedisPubSubBroadcastAdapter",
    "RedisThrottleAdapter",
    "ThrottlePort",
    "build_infra_container",
]


@dataclass
class InfraContainer:
    cache: CachePort
    throttle: ThrottlePort
    lock_service: DistributedLockPort
    event_stream: EventStreamPort
    broadcaster: RealtimeBroadcastPort
    redis_manager: RedisManager | None = None

    def shutdown(self, wait: bool = False) -> None:
        try:
            self.event_stream.shutdown(wait=wait)
        except Exception as exc:
            logger.warning("Error shutting down event_stream: %s", exc)
        try:
            self.broadcaster.shutdown()
        except Exception as exc:
            logger.warning("Error shutting down broadcaster: %s", exc)
        if self.redis_manager is not None:
            self.redis_manager.close()


def build_infra_container(settings: Settings) -> InfraContainer:
    """Build and wire infrastructure adapters based on Settings, with automatic in-memory fallback."""
    if not settings.redis_url:
        logger.info("AGENT_REDIS_URL is not set; using in-memory infrastructure adapters")
        return InfraContainer(
            cache=InMemoryCacheAdapter(default_ttl_seconds=settings.cache_stats_ttl_seconds),
            throttle=InMemoryThrottleAdapter(cooldown_seconds=settings.feishu_alert_cooldown_seconds),
            lock_service=InMemoryDistributedLockAdapter(),
            event_stream=DirectEventStreamAdapter(),
            broadcaster=InMemoryBroadcastAdapter(),
            redis_manager=None,
        )

    redis_mgr = RedisManager(
        url=settings.redis_url,
        socket_timeout=settings.redis_socket_timeout_seconds,
        key_prefix=settings.redis_key_prefix,
    )

    # Validate Redis reachability
    if not redis_mgr.ping():
        logger.warning(
            "Configured Redis at %s is unreachable; falling back to in-memory infrastructure adapters",
            settings.redis_url,
        )
        return InfraContainer(
            cache=InMemoryCacheAdapter(default_ttl_seconds=settings.cache_stats_ttl_seconds),
            throttle=InMemoryThrottleAdapter(cooldown_seconds=settings.feishu_alert_cooldown_seconds),
            lock_service=InMemoryDistributedLockAdapter(),
            event_stream=DirectEventStreamAdapter(),
            broadcaster=InMemoryBroadcastAdapter(),
            redis_manager=redis_mgr,
        )

    logger.info("Successfully connected to Redis at %s", settings.redis_url)
    cache = RedisCacheAdapter(
        redis_mgr.client,
        redis_mgr.keys,
        default_ttl_seconds=settings.cache_stats_ttl_seconds,
    )
    throttle = RedisThrottleAdapter(
        redis_mgr.client,
        redis_mgr.keys,
        cooldown_seconds=settings.feishu_alert_cooldown_seconds,
    )
    lock_service = RedisDistributedLockAdapter(
        redis_mgr.client,
        redis_mgr.keys,
        default_ttl_seconds=settings.lock_default_ttl_seconds,
        watchdog_interval_ratio=settings.lock_watchdog_interval_ratio,
    )
    event_stream = (
        RedisEventStreamAdapter(
            redis_mgr.client,
            redis_mgr.keys,
            stream_name=settings.stream_violation_events_key,
            consumer_group=settings.stream_consumer_group,
        )
        if settings.stream_async_enabled
        else DirectEventStreamAdapter()
    )
    broadcaster = RedisPubSubBroadcastAdapter(
        redis_mgr.client,
        redis_mgr.keys,
        channel_name=settings.pubsub_realtime_channel,
    )

    return InfraContainer(
        cache=cache,
        throttle=throttle,
        lock_service=lock_service,
        event_stream=event_stream,
        broadcaster=broadcaster,
        redis_manager=redis_mgr,
    )
