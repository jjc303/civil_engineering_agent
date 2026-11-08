"""Comprehensive unit and architectural tests for Redis infrastructure (Cache, Lock, Throttle, Messaging)."""
from __future__ import annotations

from datetime import datetime, timezone
import json
import time
from uuid import uuid4

import fakeredis
from fastapi.testclient import TestClient
import pytest

from agent.contracts.chat import ToolDecision
from agent.contracts.event_v1 import SafetyViolationEventV1
from agent.contracts.query import ViolationQuery
from agent.core.config import Settings
from agent.db.base import Database
from agent.db.models import AgentPendingActionModel
from agent.infra import build_infra_container
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
    RealtimeBroadcastPort,
    ThrottlePort,
)
from agent.infra.redis_client import KeyBuilder, RedisManager
from agent.main import create_app
from agent.services.agent_write_actions import (
    AgentWriteActionError,
    AgentWriteActionService,
    WriteActionHandlerSpec,
)
from agent.services.perception_service import PerceptionService


@pytest.fixture
def fake_redis_client():
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def key_builder():
    return KeyBuilder(prefix="test_cea")


def test_ports_protocol_conformance(fake_redis_client, key_builder):
    cache = RedisCacheAdapter(fake_redis_client, key_builder)
    assert isinstance(cache, CachePort)
    in_mem_cache = InMemoryCacheAdapter()
    assert isinstance(in_mem_cache, CachePort)

    throttle = RedisThrottleAdapter(fake_redis_client, key_builder)
    assert isinstance(throttle, ThrottlePort)
    in_mem_throttle = InMemoryThrottleAdapter()
    assert isinstance(in_mem_throttle, ThrottlePort)

    lock = RedisDistributedLockAdapter(fake_redis_client, key_builder)
    assert isinstance(lock, DistributedLockPort)
    in_mem_lock = InMemoryDistributedLockAdapter()
    assert isinstance(in_mem_lock, DistributedLockPort)

    stream = RedisEventStreamAdapter(fake_redis_client, key_builder)
    assert isinstance(stream, EventStreamPort)
    direct_stream = DirectEventStreamAdapter()
    assert isinstance(direct_stream, EventStreamPort)

    pubsub = RedisPubSubBroadcastAdapter(fake_redis_client, key_builder)
    assert isinstance(pubsub, RealtimeBroadcastPort)
    in_mem_pubsub = InMemoryBroadcastAdapter()
    assert isinstance(in_mem_pubsub, RealtimeBroadcastPort)


def test_cache_versioned_namespace_invalidation_without_keys_command(fake_redis_client, key_builder):
    """Test that namespace invalidation is O(1) by bumping version, never calling KEYS *."""
    cache = RedisCacheAdapter(fake_redis_client, key_builder, default_ttl_seconds=60)

    # Put keys in different namespaces
    cache.set_json("stats", "today", {"violations": 5})
    cache.set_json("stats", "heatmap", {"score": 9.2})
    cache.set_json("learning", "insights", {"advice": "强化高空作业"})

    assert cache.get_json("stats", "today") == {"violations": 5}
    assert cache.get_json("stats", "heatmap") == {"score": 9.2}
    assert cache.get_json("learning", "insights") == {"advice": "强化高空作业"}

    # Invalidate 'stats' namespace
    cache.invalidate_namespace("stats")

    # Stats keys should be missed immediately
    assert cache.get_json("stats", "today") is None
    assert cache.get_json("stats", "heatmap") is None

    # Learning namespace should remain intact
    assert cache.get_json("learning", "insights") == {"advice": "强化高空作业"}


def test_throttle_atomic_cooldown(fake_redis_client, key_builder):
    throttle = RedisThrottleAdapter(fake_redis_client, key_builder, cooldown_seconds=2)

    # First call allowed
    assert throttle.should_send("cam_01", "NO_HELMET", "zone_1") is True
    # Immediate repeat throttled
    assert throttle.should_send("cam_01", "NO_HELMET", "zone_1") is False
    # Different camera or zone allowed
    assert throttle.should_send("cam_02", "NO_HELMET", "zone_1") is True
    assert throttle.should_send("cam_01", "DANGER_ZONE_INTRUSION", "zone_1") is True


def test_distributed_lock_mutual_exclusion_and_safe_release(fake_redis_client, key_builder):
    lock_adapter = RedisDistributedLockAdapter(fake_redis_client, key_builder, default_ttl_seconds=10)

    # Worker 1 acquires lock
    handle1 = lock_adapter.acquire("sync_job", ttl_seconds=10, blocking_timeout=0, watchdog=False)
    assert handle1.is_acquired is True

    # Worker 2 tries non-blocking acquire on same resource
    handle2 = lock_adapter.acquire("sync_job", ttl_seconds=10, blocking_timeout=0, watchdog=False)
    assert handle2.is_acquired is False

    # Worker 2 attempts to release handle1's lock (should be a no-op due to Lua token check)
    handle2.release()
    # Lock is still held by Worker 1
    assert fake_redis_client.get(key_builder.lock_key("sync_job")) == handle1.token

    # Worker 1 releases lock
    handle1.release()
    assert fake_redis_client.get(key_builder.lock_key("sync_job")) is None

    # Now Worker 2 can acquire
    handle3 = lock_adapter.acquire("sync_job", ttl_seconds=10, blocking_timeout=0, watchdog=False)
    assert handle3.is_acquired is True
    handle3.release()


def test_distributed_lock_watchdog_auto_renewal(fake_redis_client, key_builder):
    """Test that watchdog automatically renews lock TTL for long-running operations."""
    lock_adapter = RedisDistributedLockAdapter(
        fake_redis_client,
        key_builder,
        default_ttl_seconds=1,
        watchdog_interval_ratio=0.3,
    )

    lock_key = key_builder.lock_key("long_task")
    with lock_adapter.acquire("long_task", ttl_seconds=1, blocking_timeout=0, watchdog=True) as handle:
        assert handle.is_acquired is True

        # Sleep longer than initial 1 second TTL (1.4 seconds)
        time.sleep(1.4)

        # Because watchdog renewed the lock, it MUST still exist with the owner's token!
        val = fake_redis_client.get(lock_key)
        assert val == handle.token

    # Once exited the with block, lock must be released immediately
    assert fake_redis_client.get(lock_key) is None


def test_in_memory_distributed_lock():
    lock_adapter = InMemoryDistributedLockAdapter()
    h1 = lock_adapter.acquire("resource_a", blocking_timeout=0)
    assert h1.is_acquired is True

    h2 = lock_adapter.acquire("resource_a", blocking_timeout=0)
    assert h2.is_acquired is False

    h1.release()
    h3 = lock_adapter.acquire("resource_a", blocking_timeout=0)
    assert h3.is_acquired is True
    h3.release()


def test_write_action_service_concurrent_confirm_rejection():
    """Test that concurrent double-confirm on same action is prevented by distributed lock."""
    db = Database("sqlite+pysqlite:///:memory:")
    db.create_schema()
    lock_service = InMemoryDistributedLockAdapter()

    service = AgentWriteActionService(
        database=db,
        camera_management=None,
        lock_service=lock_service,
        lock_ttl_seconds=10,
    )

    executed_count = 0

    def slow_exec(svc, session, payload):
        nonlocal executed_count
        executed_count += 1
        return {"status": "ok"}, None

    service.register_action_handler(WriteActionHandlerSpec(
        action_type="slow_action",
        execution_mode="transactional",
        propose_fn=lambda s, c, d: ("慢操作", {}),
        execute_fn=slow_exec,
    ))

    res = service.propose("conv-01", ToolDecision(tool_name="slow_action", arguments={}, purpose="测试慢操作"))
    conf_id = res.confirmation_id

    # Simulate lock already held by an in-flight execution of the same confirmation_id
    manual_handle = lock_service.acquire(f"action_confirm:{conf_id}", blocking_timeout=0)
    assert manual_handle.is_acquired is True

    # Attempting to confirm while lock is held must raise AgentWriteActionError
    with pytest.raises(AgentWriteActionError, match="正在执行中，请勿重复提交"):
        service.confirm(conf_id, "conv-01")

    manual_handle.release()

    # After release, confirm should succeed
    confirm_res = service.confirm(conf_id, "conv-01")
    assert confirm_res.status == "EXECUTED"
    assert executed_count == 1


def test_perception_service_cache_and_invalidation():
    db = Database("sqlite+pysqlite:///:memory:")
    db.create_schema()
    in_mem_cache = InMemoryCacheAdapter(default_ttl_seconds=60)

    service = PerceptionService(
        database=db,
        cache=in_mem_cache,
        cache_stats_ttl_seconds=60,
    )

    # 1. First stats call computes from DB and caches
    query = ViolationQuery()
    stats1 = service.get_statistics(query)
    assert stats1.total_violations == 0

    # Verify cached
    cache_key = f"stats:{query.camera_id}:{query.start_time_utc}:{query.end_time_utc}"
    assert in_mem_cache.get_json("stats", cache_key) is not None

    # 2. Add an event: upsert_event must invalidate "stats" namespace
    event = SafetyViolationEventV1(
        event_uuid=str(uuid4()),
        camera_id="cam_01",
        monitor_session_id="sess_01",
        track_id=1,
        violation_type="NO_HELMET",
        severity="CRITICAL",
        status="ACTIVE",
        duration_seconds=0.0,
        occurred_at_utc=datetime.now(timezone.utc),
    )
    upsert_res = service.upsert_event(event)
    assert upsert_res.operation == "CREATED"

    # Verify cache was invalidated
    assert in_mem_cache.get_json("stats", cache_key) is None

    # 3. Next stats call recomputes with updated count
    stats2 = service.get_statistics(query)
    assert stats2.total_violations == 1


def test_redis_event_stream_publish_and_consume(fake_redis_client, key_builder):
    stream = RedisEventStreamAdapter(
        fake_redis_client,
        key_builder,
        stream_name="test_stream",
        consumer_group="test_group",
    )
    consumed = []
    stream.start_consumer(lambda p: consumed.append(p))
    stream.publish_event({"alert": "hazard", "id": 101})

    for _ in range(20):
        if consumed:
            break
        time.sleep(0.05)

    stream.shutdown(wait=True)
    assert len(consumed) == 1
    assert consumed[0]["alert"] == "hazard"


def test_realtime_events_sse_endpoint():
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        internal_perception_token="test-token",
        llm_provider="fake",
        auto_create_schema=True,
    )
    app = create_app(settings)
    with TestClient(app) as client:
        with client.stream("GET", "/api/v1/safety/events/stream?max_events=1") as response:
            assert response.status_code == 200
            assert "text/event-stream" in response.headers["content-type"]
            lines = [line for line in response.iter_lines() if line]
            assert any("ping" in l for l in lines)


def test_live_redis_server_end_to_end():
    redis_url = "redis://127.0.0.1:6379/0"
    mgr = RedisManager(redis_url, key_prefix="cea_live_test")
    if not mgr.ping():
        pytest.skip("Local redis server is not reachable")

    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        internal_perception_token="test-live-token",
        llm_provider="fake",
        auto_create_schema=True,
        redis_url=redis_url,
        redis_key_prefix="cea_live_test",
    )
    infra = build_infra_container(settings)
    try:
        assert isinstance(infra.cache, RedisCacheAdapter)
        assert isinstance(infra.lock_service, RedisDistributedLockAdapter)
        assert isinstance(infra.throttle, RedisThrottleAdapter)

        # Test cache set and get
        infra.cache.set_json("live_test", "key1", {"status": "ok"}, ttl_seconds=10)
        assert infra.cache.get_json("live_test", "key1") == {"status": "ok"}

        # Test ttl=0 disables caching and removes existing entry
        infra.cache.set_json("live_test", "key1", {"status": "disabled"}, ttl_seconds=0)
        assert infra.cache.get_json("live_test", "key1") is None

        # Test lock
        with infra.lock_service.acquire("test_live_lock", ttl_seconds=5) as handle:
            assert handle.is_acquired is True
            h2 = infra.lock_service.acquire("test_live_lock", ttl_seconds=5, blocking_timeout=0)
            assert h2.is_acquired is False
    finally:
        try:
            infra.cache.delete("live_test", "key1")
            mgr.client.delete(mgr.keys.namespace_version_key("live_test"))
        except Exception:
            pass
        infra.shutdown()
        mgr.close()


def test_distributed_lock_runtime_fail_open_on_redis_disconnect(key_builder):
    """Verify that if Redis disconnects mid-runtime, lock acquisition falls back to in-memory lock instead of failing closed."""
    class BrokenRedisClient:
        def set(self, *args, **kwargs):
            raise ConnectionError("Redis connection lost at runtime")

    lock_adapter = RedisDistributedLockAdapter(BrokenRedisClient(), key_builder, default_ttl_seconds=10)
    with lock_adapter.acquire("critical_op", blocking_timeout=0) as handle1:
        assert handle1.is_acquired is True
        # Concurrent acquire on the fallback in-memory lock still enforces mutual exclusion
        handle2 = lock_adapter.acquire("critical_op", blocking_timeout=0)
        assert handle2.is_acquired is False


def test_stream_failed_handler_keeps_pending_and_reclaims(fake_redis_client, key_builder):
    """Verify that when handler fails, message is NOT ACKed and can be reclaimed and retried."""
    stream = RedisEventStreamAdapter(
        fake_redis_client,
        key_builder,
        stream_name="reclaim_stream",
        consumer_group="reclaim_group",
    )
    fake_redis_client.xgroup_create(stream.stream_key, stream.consumer_group, id="0", mkstream=True)
    msg_id = stream.publish_event({"event_type": "violation_event", "seq": 1})
    assert msg_id is not None

    entries = fake_redis_client.xreadgroup(
        groupname=stream.consumer_group,
        consumername=stream.consumer_id,
        streams={stream.stream_key: ">"},
        count=1,
    )
    _, messages = entries[0]
    read_msg_id, fields = messages[0]

    # 1. Handler raises an error -> must NOT be ACKed
    def failing_handler(_payload):
        raise RuntimeError("transient webhook failure")

    acked = stream._process_stream_message(str(read_msg_id), fields, failing_handler)
    assert acked is False

    # 2. Reclaim pending with min_idle_ms=0 and succeeding handler -> must succeed and ACK
    recovered = []
    reclaimed_count = stream.reclaim_pending_messages(lambda p: recovered.append(p), min_idle_ms=0)
    assert reclaimed_count == 1
    assert len(recovered) == 1
    assert recovered[0]["seq"] == 1

