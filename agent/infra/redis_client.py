"""Redis connection management, KeyBuilder, and health checking."""
from __future__ import annotations

import logging
from typing import Any

import redis

logger = logging.getLogger(__name__)


class KeyBuilder:
    """Builds consistent namespaced Redis keys without hardcoding."""

    def __init__(self, prefix: str = "cea") -> None:
        self.prefix = prefix.strip().rstrip(":")

    def key(self, namespace: str, name: str) -> str:
        ns = namespace.strip().strip(":")
        nm = name.strip().strip(":")
        return f"{self.prefix}:{ns}:{nm}"

    def namespace_version_key(self, namespace: str) -> str:
        ns = namespace.strip().strip(":")
        return f"{self.prefix}:_ns_ver:{ns}"

    def lock_key(self, name: str) -> str:
        nm = name.strip().strip(":")
        return f"{self.prefix}:lock:{nm}"

    def throttle_key(self, camera_id: str, violation_type: str, zone_id: str | None = None) -> str:
        zid = (zone_id or "").strip()
        return f"{self.prefix}:throttle:{camera_id}:{violation_type}:{zid}"

    def stream_key(self, name: str) -> str:
        nm = name.strip().strip(":")
        return f"{self.prefix}:{nm}"

    def pubsub_channel(self, name: str) -> str:
        nm = name.strip().strip(":")
        return f"{self.prefix}:{nm}"


class RedisManager:
    """Manages Redis connection pool and error handling with fail-open safety."""

    def __init__(self, url: str, socket_timeout: float = 2.0, key_prefix: str = "cea") -> None:
        self.url = url
        self.socket_timeout = socket_timeout
        self.keys = KeyBuilder(key_prefix)
        self._client: redis.Redis[Any] | None = None

    @property
    def client(self) -> redis.Redis[Any]:
        if self._client is None:
            self._client = redis.from_url(
                self.url,
                socket_timeout=self.socket_timeout,
                socket_connect_timeout=self.socket_timeout,
                decode_responses=True,
            )
        return self._client

    def ping(self) -> bool:
        if not self.url:
            return False
        try:
            return bool(self.client.ping())
        except Exception as exc:
            logger.warning("Redis ping failed: %s", exc)
            return False

    def close(self) -> None:
        if self._client is not None:
            try:
                self._client.close()
            except Exception as exc:
                logger.warning("Error closing Redis client: %s", exc)
            finally:
                self._client = None
