"""Redis Streams message queue and Pub/Sub realtime broadcast adapters."""
from __future__ import annotations

import json
import logging
import queue
import threading
import time
from collections.abc import Callable, Iterator
from typing import Any
from uuid import uuid4

from agent.infra.ports import EventStreamPort, RealtimeBroadcastPort
from agent.infra.redis_client import KeyBuilder

logger = logging.getLogger(__name__)


class DirectEventStreamAdapter(EventStreamPort):
    """Direct execution event stream adapter for environments without Redis (DIP & LSP)."""

    def __init__(self) -> None:
        self._handler: Callable[[dict[str, Any]], None] | None = None
        self._lock = threading.Lock()

    def publish_event(self, event_payload: dict[str, Any]) -> str | None:
        with self._lock:
            handler = self._handler
        if handler:
            try:
                handler(event_payload)
            except Exception as exc:
                logger.exception("Direct event handler execution failed: %s", exc)
        return str(uuid4())

    def start_consumer(self, handler: Callable[[dict[str, Any]], None]) -> None:
        with self._lock:
            self._handler = handler

    def shutdown(self, wait: bool = False) -> None:
        with self._lock:
            self._handler = None


class RedisEventStreamAdapter(EventStreamPort):
    """Redis Streams reliable event stream with consumer group acknowledgment (ACK)."""

    def __init__(
        self,
        client: Any,
        keys: KeyBuilder,
        stream_name: str = "streams:violation_events",
        consumer_group: str = "agent_notification_workers",
        max_stream_len: int = 10000,
    ) -> None:
        self.client = client
        self.keys = keys
        self.stream_key = self.keys.stream_key(stream_name)
        self.consumer_group = consumer_group
        self.max_stream_len = max_stream_len
        self.consumer_id = f"worker-{uuid4().hex[:8]}"
        self._stop_event = threading.Event()
        self._consumer_thread: threading.Thread | None = None
        self._fallback = DirectEventStreamAdapter()

    def publish_event(self, event_payload: dict[str, Any]) -> str | None:
        try:
            data = {"payload": json.dumps(event_payload, ensure_ascii=False)}
            msg_id = self.client.xadd(
                self.stream_key,
                data,
                maxlen=self.max_stream_len,
                approximate=True,
            )
            return str(msg_id)
        except Exception as exc:
            logger.warning("Redis stream publish failed for %s, falling back: %s", self.stream_key, exc)
            return self._fallback.publish_event(event_payload)

    def _process_stream_message(
        self,
        msg_id: str,
        fields: dict[str, Any],
        handler: Callable[[dict[str, Any]], None],
    ) -> bool:
        raw_payload = fields.get("payload")
        should_ack = True
        if raw_payload:
            try:
                payload = json.loads(raw_payload)
            except Exception as parse_err:
                logger.warning("Dropping malformed stream message %s: %s", msg_id, parse_err)
                should_ack = True
            else:
                try:
                    handler(payload)
                except Exception as err:
                    logger.exception("Error processing stream message %s (kept pending for retry): %s", msg_id, err)
                    should_ack = False
        if should_ack:
            try:
                self.client.xack(self.stream_key, self.consumer_group, msg_id)
                return True
            except Exception as ack_err:
                logger.warning("Failed to ACK stream message %s: %s", msg_id, ack_err)
        return False

    def reclaim_pending_messages(
        self,
        handler: Callable[[dict[str, Any]], None],
        min_idle_ms: int = 30000,
        count: int = 10,
    ) -> int:
        """Reclaim and re-process timed-out pending messages (XAUTOCLAIM with XPENDING/XCLAIM fallback for Redis 6.0)."""
        reclaimed_messages: list[tuple[str, dict[str, Any]]] = []
        try:
            res = self.client.xautoclaim(
                self.stream_key,
                self.consumer_group,
                self.consumer_id,
                min_idle_time=min_idle_ms,
                start_id="0-0",
                count=count,
            )
            if isinstance(res, (list, tuple)) and len(res) >= 2:
                reclaimed_messages = list(res[1] or [])
        except Exception:
            try:
                pending_items = self.client.xpending_range(
                    self.stream_key,
                    self.consumer_group,
                    min="-",
                    max="+",
                    count=count,
                )
                msg_ids = [
                    item["message_id"]
                    for item in (pending_items or [])
                    if item.get("time_since_delivered", 0) >= min_idle_ms
                ]
                if msg_ids:
                    reclaimed_messages = list(
                        self.client.xclaim(
                            self.stream_key,
                            self.consumer_group,
                            self.consumer_id,
                            min_idle_time=min_idle_ms,
                            message_ids=msg_ids,
                        )
                        or []
                    )
            except Exception as fallback_exc:
                logger.debug("Pending message reclaim skipped: %s", fallback_exc)

        acked = 0
        for msg_id, fields in reclaimed_messages:
            if fields and self._process_stream_message(str(msg_id), fields, handler):
                acked += 1
        return acked

    def start_consumer(self, handler: Callable[[dict[str, Any]], None]) -> None:
        self._fallback.start_consumer(handler)
        # Create consumer group if not existing
        try:
            self.client.xgroup_create(self.stream_key, self.consumer_group, id="0", mkstream=True)
        except Exception as exc:
            # BUSYGROUP is expected when group was already initialized
            if "BUSYGROUP" not in str(exc):
                logger.warning("Could not create stream group %s: %s", self.consumer_group, exc)

        def _consume_loop() -> None:
            logger.info("Stream consumer %s started for %s", self.consumer_id, self.stream_key)
            last_reclaim = time.monotonic()
            while not self._stop_event.is_set():
                try:
                    now = time.monotonic()
                    if (now - last_reclaim) >= 15.0:
                        self.reclaim_pending_messages(handler)
                        last_reclaim = now

                    entries = self.client.xreadgroup(
                        groupname=self.consumer_group,
                        consumername=self.consumer_id,
                        streams={self.stream_key: ">"},
                        count=10,
                        block=1000,
                    )
                    if not entries:
                        continue
                    for _, messages in entries:
                        for msg_id, fields in messages:
                            self._process_stream_message(str(msg_id), fields, handler)
                except Exception as exc:
                    if not self._stop_event.is_set():
                        logger.warning("Error in Redis stream consume loop: %s", exc)
                        time.sleep(1.0)

        self._consumer_thread = threading.Thread(
            target=_consume_loop,
            name=f"stream-{self.consumer_group}",
            daemon=True,
        )
        self._consumer_thread.start()

    def shutdown(self, wait: bool = False) -> None:
        self._stop_event.set()
        self._fallback.shutdown(wait=wait)
        if self._consumer_thread and self._consumer_thread.is_alive():
            self._consumer_thread.join(timeout=1.0 if wait else 0.1)


class InMemoryBroadcastAdapter(RealtimeBroadcastPort):
    """In-memory pub/sub broadcast adapter for local standalone operation."""

    def __init__(self) -> None:
        self._subscribers: set[queue.Queue[dict[str, Any] | None]] = set()
        self._lock = threading.Lock()
        self._stopped = False

    def publish(self, event_type: str, payload: dict[str, Any]) -> int:
        msg = {
            "event_type": event_type,
            "data": payload,
            "published_at_utc": time.time(),
        }
        with self._lock:
            for q in list(self._subscribers):
                try:
                    q.put_nowait(msg)
                except queue.Full:
                    pass
            return len(self._subscribers)

    def subscribe(self) -> Iterator[dict[str, Any] | None]:
        q: queue.Queue[dict[str, Any] | None] = queue.Queue(maxsize=100)
        with self._lock:
            self._subscribers.add(q)
        try:
            while not self._stopped:
                try:
                    item = q.get(timeout=0.2)
                except queue.Empty:
                    yield None
                    continue
                if item is None:
                    break
                yield item
        finally:
            with self._lock:
                self._subscribers.discard(q)

    def shutdown(self) -> None:
        self._stopped = True
        with self._lock:
            for q in list(self._subscribers):
                try:
                    q.put_nowait(None)  # Signal termination
                except Exception:
                    pass
            self._subscribers.clear()


class RedisPubSubBroadcastAdapter(RealtimeBroadcastPort):
    """Redis Pub/Sub adapter broadcasting real-time events to connected clients."""

    def __init__(self, client: Any, keys: KeyBuilder, channel_name: str = "pubsub:realtime_events") -> None:
        self.client = client
        self.keys = keys
        self.channel = self.keys.pubsub_channel(channel_name)
        self._fallback = InMemoryBroadcastAdapter()
        self._stop_event = threading.Event()

    def publish(self, event_type: str, payload: dict[str, Any]) -> int:
        msg = {
            "event_type": event_type,
            "data": payload,
            "published_at_utc": time.time(),
        }
        encoded = json.dumps(msg, ensure_ascii=False)
        self._fallback.publish(event_type, payload)
        try:
            return int(self.client.publish(self.channel, encoded))
        except Exception as exc:
            logger.warning("Redis pubsub publish failed for %s: %s", self.channel, exc)
            return 0

    def subscribe(self) -> Iterator[dict[str, Any] | None]:
        pubsub = None
        try:
            pubsub = self.client.pubsub()
            pubsub.subscribe(self.channel)
        except Exception as exc:
            logger.warning("Failed to subscribe to Redis channel %s, falling back: %s", self.channel, exc)
            yield from self._fallback.subscribe()
            return

        try:
            while not self._stop_event.is_set():
                try:
                    message = pubsub.get_message(ignore_subscribe_messages=True, timeout=0.2)
                    if message and message.get("type") == "message":
                        raw_data = message.get("data")
                        if raw_data:
                            yield json.loads(raw_data)
                    else:
                        yield None
                except Exception as exc:
                    logger.warning("Error reading from Redis Pub/Sub, falling back to in-memory: %s", exc)
                    yield from self._fallback.subscribe()
                    break
        finally:
            if pubsub is not None:
                try:
                    pubsub.unsubscribe(self.channel)
                    pubsub.close()
                except Exception:
                    pass

    def shutdown(self) -> None:
        self._stop_event.set()
        self._fallback.shutdown()
