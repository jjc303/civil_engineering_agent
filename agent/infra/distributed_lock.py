"""Distributed mutual exclusion with Lua scripts and background watchdog renewal."""
from __future__ import annotations

import logging
import threading
import time
from typing import Any
from uuid import uuid4

from agent.infra.ports import DistributedLockPort, LockHandle
from agent.infra.redis_client import KeyBuilder

logger = logging.getLogger(__name__)

# Atomic release script: Only delete if the current value matches the owner's token
_UNLOCK_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("del", KEYS[1])
else
    return 0
end
"""

# Atomic renewal script for watchdog: Only extend TTL if token still matches
_RENEW_LUA = """
if redis.call("get", KEYS[1]) == ARGV[1] then
    return redis.call("pexpire", KEYS[1], ARGV[2])
else
    return 0
end
"""


class RedisLockHandle(LockHandle):
    """Concrete LockHandle for Redis with background watchdog auto-renewal."""

    def __init__(
        self,
        client: Any,
        lock_key: str,
        token: str,
        ttl_ms: int,
        acquired: bool,
        watchdog: bool = True,
        watchdog_interval_ratio: float = 0.33,
    ) -> None:
        self.client = client
        self.lock_key = lock_key
        self.token = token
        self.ttl_ms = ttl_ms
        self._acquired = acquired
        self._watchdog = watchdog
        self._watchdog_interval_ratio = max(0.05, min(0.8, watchdog_interval_ratio))
        self._stop_event = threading.Event()
        self._watchdog_thread: threading.Thread | None = None
        self._released = False

        if self._acquired and self._watchdog:
            self._start_watchdog()

    @property
    def is_acquired(self) -> bool:
        return self._acquired and not self._released

    def _start_watchdog(self) -> None:
        interval = (self.ttl_ms / 1000.0) * self._watchdog_interval_ratio

        def _watchdog_loop() -> None:
            while not self._stop_event.wait(interval):
                try:
                    res = self.client.eval(_RENEW_LUA, 1, self.lock_key, self.token, self.ttl_ms)
                    if not res:
                        # Lock expired or taken by another process
                        logger.warning("Watchdog detected lock loss for %s", self.lock_key)
                        break
                except Exception as exc:
                    logger.warning("Watchdog renewal failed for %s: %s", self.lock_key, exc)

        self._watchdog_thread = threading.Thread(
            target=_watchdog_loop,
            name=f"watchdog-{self.lock_key}",
            daemon=True,
        )
        self._watchdog_thread.start()

    def release(self) -> None:
        if self._released:
            return
        self._released = True
        self._stop_event.set()
        if self._watchdog_thread and self._watchdog_thread.is_alive():
            self._watchdog_thread.join(timeout=0.5)

        if self._acquired:
            try:
                self.client.eval(_UNLOCK_LUA, 1, self.lock_key, self.token)
            except Exception as exc:
                logger.warning("Failed to release Redis lock %s: %s", self.lock_key, exc)

    def __enter__(self) -> "RedisLockHandle":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.release()


class RedisDistributedLockAdapter(DistributedLockPort):
    """Production Redis distributed lock with Lua atomicity, watchdog renewal, and fail-open fallback."""

    def __init__(
        self,
        client: Any,
        keys: KeyBuilder,
        default_ttl_seconds: int = 30,
        watchdog_interval_ratio: float = 0.33,
    ) -> None:
        self.client = client
        self.keys = keys
        self.default_ttl_seconds = max(1, default_ttl_seconds)
        self.watchdog_interval_ratio = watchdog_interval_ratio
        self._fallback = InMemoryDistributedLockAdapter()

    def acquire(
        self,
        lock_name: str,
        ttl_seconds: int = 30,
        blocking_timeout: float | None = None,
        watchdog: bool = True,
    ) -> LockHandle:
        ttl = max(1, ttl_seconds if ttl_seconds > 0 else self.default_ttl_seconds)
        ttl_ms = int(ttl * 1000)
        lock_key = self.keys.lock_key(lock_name)
        token = str(uuid4())

        # Non-blocking attempt
        if blocking_timeout == 0:
            try:
                res = self.client.set(lock_key, token, px=ttl_ms, nx=True)
                acquired = bool(res)
            except Exception as exc:
                logger.warning("Non-blocking Redis lock acquire failed for %s, falling back to in-memory: %s", lock_key, exc)
                return self._fallback.acquire(lock_name, ttl_seconds=ttl, blocking_timeout=0, watchdog=watchdog)
            return RedisLockHandle(
                self.client,
                lock_key,
                token,
                ttl_ms,
                acquired,
                watchdog=watchdog,
                watchdog_interval_ratio=self.watchdog_interval_ratio,
            )

        # Blocking attempt with timeout or indefinite
        start_time = time.monotonic()
        retry_interval = 0.05
        acquired = False
        while True:
            try:
                res = self.client.set(lock_key, token, px=ttl_ms, nx=True)
                if res:
                    acquired = True
                    break
            except Exception as exc:
                logger.warning("Redis lock acquire error for %s, falling back to in-memory: %s", lock_key, exc)
                return self._fallback.acquire(lock_name, ttl_seconds=ttl, blocking_timeout=blocking_timeout, watchdog=watchdog)

            if blocking_timeout is not None:
                if (time.monotonic() - start_time) >= blocking_timeout:
                    break

            time.sleep(retry_interval)
            retry_interval = min(0.5, retry_interval * 1.5)

        return RedisLockHandle(
            self.client,
            lock_key,
            token,
            ttl_ms,
            acquired,
            watchdog=watchdog,
            watchdog_interval_ratio=self.watchdog_interval_ratio,
        )


class InMemoryLockHandle(LockHandle):
    """In-memory LockHandle holding a threading.Lock."""

    def __init__(self, raw_lock: threading.Lock, acquired: bool) -> None:
        self.raw_lock = raw_lock
        self._acquired = acquired
        self._released = False

    @property
    def is_acquired(self) -> bool:
        return self._acquired and not self._released

    def release(self) -> None:
        if self._released:
            return
        self._released = True
        if self._acquired:
            try:
                self.raw_lock.release()
            except RuntimeError:
                pass

    def __enter__(self) -> "InMemoryLockHandle":
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.release()


class InMemoryDistributedLockAdapter(DistributedLockPort):
    """Thread-safe in-memory mutual exclusion adapter for standalone/test environments."""

    def __init__(self) -> None:
        self._global_lock = threading.Lock()
        self._locks: dict[str, threading.Lock] = {}

    def _get_lock(self, name: str) -> threading.Lock:
        with self._global_lock:
            if name not in self._locks:
                self._locks[name] = threading.Lock()
            return self._locks[name]

    def acquire(
        self,
        lock_name: str,
        ttl_seconds: int = 30,
        blocking_timeout: float | None = None,
        watchdog: bool = True,
    ) -> LockHandle:
        raw_lock = self._get_lock(lock_name)
        if blocking_timeout == 0:
            acquired = raw_lock.acquire(blocking=False)
            return InMemoryLockHandle(raw_lock, acquired)

        timeout = -1 if blocking_timeout is None else max(0.0, float(blocking_timeout))
        acquired = raw_lock.acquire(timeout=timeout)
        return InMemoryLockHandle(raw_lock, acquired)
