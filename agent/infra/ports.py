"""Infrastructure port interfaces adhering to ISP and DIP (SOLID)."""
from __future__ import annotations

from collections.abc import Callable, Iterator
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class CachePort(Protocol):
    """Fine-grained port for key-value caching with versioned namespace invalidation (ISP)."""

    def get_json(self, namespace: str, key: str) -> Any | None:
        """Retrieve and deserialize JSON value. Returns None if key misses or expires."""
        ...

    def set_json(self, namespace: str, key: str, value: Any, ttl_seconds: int | None = None) -> None:
        """Serialize and store JSON value with optional TTL."""
        ...

    def delete(self, namespace: str, key: str) -> bool:
        """Delete specific key in namespace."""
        ...

    def invalidate_namespace(self, namespace: str) -> None:
        """Invalidate all keys under namespace in O(1) time without calling KEYS *."""
        ...


@runtime_checkable
class ThrottlePort(Protocol):
    """Fine-grained port for alert throttling / duplicate suppression across instances (ISP)."""

    def should_send(self, camera_id: str, violation_type: str, zone_id: str | None = None) -> bool:
        """Return True if notification is allowed; False if currently throttled/cooling down."""
        ...

    def reset(self) -> None:
        """Reset throttle records."""
        ...


@runtime_checkable
class LockHandle(Protocol):
    """Context manager and explicit control handle for an acquired or attempted lock."""

    @property
    def is_acquired(self) -> bool:
        """True if lock was acquired successfully."""
        ...

    def release(self) -> None:
        """Explicitly release lock and cancel watchdog renewal."""
        ...

    def __enter__(self) -> "LockHandle":
        ...

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        ...


@runtime_checkable
class DistributedLockPort(Protocol):
    """Fine-grained port for distributed mutual exclusion with optional watchdog renewal (ISP)."""

    def acquire(
        self,
        lock_name: str,
        ttl_seconds: int = 30,
        blocking_timeout: float | None = None,
        watchdog: bool = True,
    ) -> LockHandle:
        """Acquire a distributed lock with automatic watchdog renewal option.
        
        If blocking_timeout is 0, attempt non-blocking acquisition immediately.
        If blocking_timeout > 0, wait up to that many seconds.
        If blocking_timeout is None, wait indefinitely until acquired.
        """
        ...


@runtime_checkable
class EventStreamPort(Protocol):
    """Fine-grained port for reliable event stream message queue with consumer group ACK (ISP)."""

    def publish_event(self, event_payload: dict[str, Any]) -> str | None:
        """Publish event to reliable stream. Returns message ID or None on failure."""
        ...

    def start_consumer(self, handler: Callable[[dict[str, Any]], None]) -> None:
        """Start background consumer group worker to process stream events."""
        ...

    def shutdown(self, wait: bool = False) -> None:
        """Stop background consumer threads cleanly."""
        ...


@runtime_checkable
class RealtimeBroadcastPort(Protocol):
    """Fine-grained port for real-time pub/sub broadcast notifications (ISP)."""

    def publish(self, event_type: str, payload: dict[str, Any]) -> int:
        """Publish real-time notification to pubsub channel. Returns number of subscribers."""
        ...

    def subscribe(self) -> Iterator[dict[str, Any]]:
        """Yield real-time broadcast events as they arrive."""
        ...

    def shutdown(self) -> None:
        """Shutdown pubsub listeners and free connections."""
        ...
