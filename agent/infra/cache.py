"""Cache and throttle adapters with fail-open safety and O(1) versioned namespace invalidation."""
from __future__ import annotations

import json
import logging
import threading
import time
from typing import Any

from agent.infra.ports import CachePort, ThrottlePort
from agent.infra.redis_client import KeyBuilder

logger = logging.getLogger(__name__)


class InMemoryCacheAdapter(CachePort):
    """Thread-safe in-memory cache adapter implementing CachePort (LSP & ISP)."""

    def __init__(self, default_ttl_seconds: int = 60) -> None:
        self.default_ttl = max(0, default_ttl_seconds)
        self._lock = threading.Lock()
        self._store: dict[tuple[str, str], tuple[float, Any]] = {}
        self._ns_versions: dict[str, int] = {}

    def get_json(self, namespace: str, key: str) -> Any | None:
        with self._lock:
            entry = self._store.get((namespace, key))
            if entry is None:
                return None
            expire_at, value = entry
            if expire_at <= time.monotonic():
                self._store.pop((namespace, key), None)
                return None
            return value

    def set_json(self, namespace: str, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        ttl = self.default_ttl if ttl_seconds is None else ttl_seconds
        if ttl <= 0:
            self.delete(namespace, key)
            return
        expire_at = time.monotonic() + ttl
        with self._lock:
            self._store[(namespace, key)] = (expire_at, value)

    def delete(self, namespace: str, key: str) -> bool:
        with self._lock:
            return self._store.pop((namespace, key), None) is not None

    def invalidate_namespace(self, namespace: str) -> None:
        with self._lock:
            keys_to_del = [k for k in self._store if k[0] == namespace]
            for k in keys_to_del:
                self._store.pop(k, None)


class RedisCacheAdapter(CachePort):
    """Redis-backed cache adapter with O(1) versioned namespace invalidation and fail-open resilience."""

    def __init__(self, client: Any, keys: KeyBuilder, default_ttl_seconds: int = 60) -> None:
        self.client = client
        self.keys = keys
        self.default_ttl = max(0, default_ttl_seconds)
        self._fallback = InMemoryCacheAdapter(default_ttl_seconds)

    def _get_namespace_version(self, namespace: str) -> str:
        try:
            vkey = self.keys.namespace_version_key(namespace)
            val = self.client.get(vkey)
            if val is not None:
                return str(val)
            if self.client.set(vkey, "1", nx=True):
                return "1"
            val = self.client.get(vkey)
            return str(val) if val is not None else "1"
        except Exception as exc:
            logger.warning("Redis failed to read namespace version for %s: %s", namespace, exc)
            return "1"

    def _namespaced_key(self, namespace: str, key: str) -> str:
        ver = self._get_namespace_version(namespace)
        return self.keys.key(namespace, f"v{ver}:{key}")

    def get_json(self, namespace: str, key: str) -> Any | None:
        try:
            rkey = self._namespaced_key(namespace, key)
            val = self.client.get(rkey)
            if val is None:
                return None
            return json.loads(val)
        except Exception as exc:
            logger.warning("Redis get_json failed for [%s:%s], falling back: %s", namespace, key, exc)
            return self._fallback.get_json(namespace, key)

    def set_json(self, namespace: str, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        ttl = self.default_ttl if ttl_seconds is None else ttl_seconds
        if ttl <= 0:
            self.delete(namespace, key)
            return
        payload = json.dumps(value, ensure_ascii=False)
        try:
            rkey = self._namespaced_key(namespace, key)
            self.client.set(rkey, payload, ex=ttl)
            # Also mirror to fallback for immediate failover consistency
            self._fallback.set_json(namespace, key, value, ttl_seconds=ttl)
        except Exception as exc:
            logger.warning("Redis set_json failed for [%s:%s]: %s", namespace, key, exc)
            self._fallback.set_json(namespace, key, value, ttl_seconds=ttl)

    def delete(self, namespace: str, key: str) -> bool:
        self._fallback.delete(namespace, key)
        try:
            rkey = self._namespaced_key(namespace, key)
            return bool(self.client.delete(rkey))
        except Exception as exc:
            logger.warning("Redis delete failed for [%s:%s]: %s", namespace, key, exc)
            return False

    def invalidate_namespace(self, namespace: str) -> None:
        """Increment namespace version so all previous keys expire by TTL in O(1) without calling KEYS *."""
        self._fallback.invalidate_namespace(namespace)
        try:
            vkey = self.keys.namespace_version_key(namespace)
            self.client.set(vkey, "1", nx=True)
            self.client.incr(vkey)
        except Exception as exc:
            logger.warning("Redis invalidate_namespace failed for %s: %s", namespace, exc)


class InMemoryThrottleAdapter(ThrottlePort):
    """Thread-safe sliding window alert throttle."""

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
            if len(self._last_sent) > 2048:
                cutoff = now - self.cooldown_seconds
                self._last_sent = {k: v for k, v in self._last_sent.items() if v >= cutoff}
            return True

    def reset(self) -> None:
        with self._lock:
            self._last_sent.clear()


class RedisThrottleAdapter(ThrottlePort):
    """Distributed atomic alert throttle using Redis SET NX with fallback."""

    def __init__(self, client: Any, keys: KeyBuilder, cooldown_seconds: int = 60) -> None:
        self.client = client
        self.keys = keys
        self.cooldown_seconds = max(0, cooldown_seconds)
        self._fallback = InMemoryThrottleAdapter(cooldown_seconds)

    def should_send(self, camera_id: str, violation_type: str, zone_id: str | None = None) -> bool:
        if self.cooldown_seconds <= 0:
            return True
        rkey = self.keys.throttle_key(camera_id, violation_type, zone_id)
        try:
            # SET key 1 EX cooldown NX -> Returns True if set (not cooling down), None if key exists (cooling down)
            res = self.client.set(rkey, "1", ex=self.cooldown_seconds, nx=True)
            return bool(res)
        except Exception as exc:
            logger.warning("Redis throttle failed for %s, falling back to in-memory: %s", rkey, exc)
            return self._fallback.should_send(camera_id, violation_type, zone_id)

    def reset(self) -> None:
        self._fallback.reset()
        # Non-blocking reset; key expiration will naturally clear Redis keys
