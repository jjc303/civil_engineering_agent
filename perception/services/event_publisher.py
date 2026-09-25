from __future__ import annotations

import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import requests

from perception.schemas.contract_v1 import (
    AgentEventResponseV1,
    CameraRunConfigContractV1,
    CameraStatusContractV1,
    PerceptionEventContractV1,
)

logger = logging.getLogger(__name__)


class OutboxStore:
    """
    Dedicated local SQLite Outbox database storing events awaiting delivery to Agent API.
    Guarantees zero event loss during transient network disconnects or Agent restarts.
    """

    def __init__(self, db_path: Union[str, Path] = "runs/outbox.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self) -> None:
        with self._get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS outbox_events (
                    event_uuid TEXT PRIMARY KEY,
                    payload_json TEXT NOT NULL,
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    next_retry_at REAL NOT NULL DEFAULT 0,
                    last_error TEXT,
                    created_at REAL NOT NULL,
                    delivered_at REAL
                );
                """
            )
            conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_outbox_pending
                ON outbox_events(delivered_at, next_retry_at);
                """
            )
            conn.commit()

    def enqueue(self, event_uuid: str, payload_dict: Dict[str, Any]) -> None:
        """
        Enqueues or updates an event payload.
        If an event with the same event_uuid already exists (e.g. state escalated or resolved),
        updates the payload and resets delivery status to ensure latest state is published.
        """
        now = time.time()
        payload_str = json.dumps(payload_dict, ensure_ascii=False)
        with self._get_connection() as conn:
            conn.execute(
                """
                INSERT INTO outbox_events (event_uuid, payload_json, retry_count, next_retry_at, last_error, created_at, delivered_at)
                VALUES (?, ?, 0, 0, NULL, ?, NULL)
                ON CONFLICT(event_uuid) DO UPDATE SET
                    payload_json = excluded.payload_json,
                    next_retry_at = 0,
                    last_error = NULL,
                    delivered_at = NULL;
                """,
                (event_uuid, payload_str, now),
            )
            conn.commit()

    def mark_delivered(self, event_uuid: str, delivered_at: Optional[float] = None) -> None:
        ts = delivered_at if delivered_at is not None else time.time()
        with self._get_connection() as conn:
            conn.execute(
                """
                UPDATE outbox_events
                SET delivered_at = ?, last_error = NULL
                WHERE event_uuid = ?;
                """,
                (ts, event_uuid),
            )
            conn.commit()

    def record_failure(
        self,
        event_uuid: str,
        error_msg: str,
        can_retry: bool = True,
        backoff_base: float = 2.0,
        max_backoff: float = 300.0,
    ) -> None:
        now = time.time()
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT retry_count FROM outbox_events WHERE event_uuid = ?",
                (event_uuid,),
            ).fetchone()
            curr_count = row["retry_count"] if row else 0
            new_count = curr_count + 1

            if can_retry:
                delay = min(max_backoff, backoff_base ** min(new_count, 10))
                next_retry = now + delay
            else:
                # Permanent failure (400, 422): do not automatically retry
                next_retry = 1e12

            conn.execute(
                """
                UPDATE outbox_events
                SET retry_count = ?, next_retry_at = ?, last_error = ?
                WHERE event_uuid = ?;
                """,
                (new_count, next_retry, error_msg[:1000], event_uuid),
            )
            conn.commit()

    def get_pending(self, limit: int = 50) -> List[Dict[str, Any]]:
        now = time.time()
        with self._get_connection() as conn:
            rows = conn.execute(
                """
                SELECT event_uuid, payload_json, retry_count, next_retry_at, last_error, created_at, delivered_at
                FROM outbox_events
                WHERE delivered_at IS NULL AND next_retry_at <= ?
                ORDER BY created_at ASC
                LIMIT ?;
                """,
                (now, limit),
            ).fetchall()
            return [dict(r) for r in rows]

    def get_event(self, event_uuid: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT * FROM outbox_events WHERE event_uuid = ?",
                (event_uuid,),
            ).fetchone()
            return dict(row) if row else None

    def get_all_events(self, delivered: Optional[bool] = None) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            if delivered is True:
                rows = conn.execute("SELECT * FROM outbox_events WHERE delivered_at IS NOT NULL ORDER BY created_at ASC;").fetchall()
            elif delivered is False:
                rows = conn.execute("SELECT * FROM outbox_events WHERE delivered_at IS NULL ORDER BY created_at ASC;").fetchall()
            else:
                rows = conn.execute("SELECT * FROM outbox_events ORDER BY created_at ASC;").fetchall()
            return [dict(r) for r in rows]


class PerceptionEventPublisher:
    """
    HTTP publisher that delivers Perception events to Agent FastAPI with Outbox resilience.
    """

    def __init__(
        self,
        agent_base_url: str = "http://127.0.0.1:8000",
        db_path: Union[str, Path] = "runs/outbox.db",
        outbox_store: Optional[OutboxStore] = None,
        bearer_token: Optional[str] = None,
        timeout: float = 5.0,
        session: Optional[requests.Session] = None,
    ):
        self.agent_base_url = agent_base_url.rstrip("/")
        self.outbox = outbox_store if outbox_store is not None else OutboxStore(db_path)
        self.bearer_token = bearer_token
        self.timeout = timeout
        self.session = session or requests.Session()

    def _headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.bearer_token:
            headers["Authorization"] = f"Bearer {self.bearer_token}"
        return headers

    def publish(
        self, event: PerceptionEventContractV1
    ) -> Tuple[bool, Optional[AgentEventResponseV1]]:
        """
        Publishes an event to Agent API:
        1. Always persists event in SQLite Outbox first.
        2. Tries synchronous HTTP POST.
        3. Marks delivered on 200/201.
        4. Applies exponential backoff on 5xx/429/connection error.
        5. Forbids automatic retry on 400/422 (logs error and requires human/schema audit).
        """
        payload = event.model_dump() if hasattr(event, "model_dump") else event.dict()
        self.outbox.enqueue(event.event_uuid, payload)

        url = f"{self.agent_base_url}/internal/v1/perception/events"
        try:
            resp = self.session.post(
                url,
                json=payload,
                headers=self._headers(),
                timeout=self.timeout,
            )
            if resp.status_code in (200, 201):
                self.outbox.mark_delivered(event.event_uuid)
                resp_json = resp.json()
                parsed = AgentEventResponseV1(**resp_json)
                return True, parsed
            elif resp.status_code in (400, 422):
                err_msg = f"HTTP {resp.status_code} Unprocessable/ClientError: {resp.text}"
                logger.error(f"[Publisher] Permanent rejection for event {event.event_uuid}: {err_msg}")
                self.outbox.record_failure(event.event_uuid, err_msg, can_retry=False)
                return False, None
            else:
                err_msg = f"HTTP {resp.status_code} ServerError: {resp.text}"
                logger.warning(f"[Publisher] Transient failure for event {event.event_uuid}: {err_msg}")
                self.outbox.record_failure(event.event_uuid, err_msg, can_retry=True)
                return False, None

        except (requests.Timeout, requests.ConnectionError, requests.RequestException) as exc:
            err_msg = f"NetworkException: {type(exc).__name__} ({str(exc)})"
            logger.warning(f"[Publisher] Network failure for event {event.event_uuid}: {err_msg}")
            self.outbox.record_failure(event.event_uuid, err_msg, can_retry=True)
            return False, None

    def flush_outbox(self, max_batch: int = 50) -> int:
        """
        Flushes pending events from Outbox whose retry timers have expired.
        Returns the number of successfully delivered events.
        """
        pending = self.outbox.get_pending(limit=max_batch)
        success_count = 0
        url = f"{self.agent_base_url}/internal/v1/perception/events"

        for item in pending:
            event_uuid = item["event_uuid"]
            payload = json.loads(item["payload_json"])

            try:
                resp = self.session.post(
                    url,
                    json=payload,
                    headers=self._headers(),
                    timeout=self.timeout,
                )
                if resp.status_code in (200, 201):
                    self.outbox.mark_delivered(event_uuid)
                    success_count += 1
                elif resp.status_code in (400, 422):
                    self.outbox.record_failure(
                        event_uuid,
                        f"HTTP {resp.status_code}: {resp.text}",
                        can_retry=False,
                    )
                else:
                    self.outbox.record_failure(
                        event_uuid,
                        f"HTTP {resp.status_code}: {resp.text}",
                        can_retry=True,
                    )
            except Exception as exc:
                self.outbox.record_failure(
                    event_uuid,
                    f"FlushException: {type(exc).__name__}",
                    can_retry=True,
                )

        return success_count

    def report_camera_status(self, status: CameraStatusContractV1) -> bool:
        """
        Reports camera operational status via PUT /internal/v1/perception/cameras/{camera_id}/status.
        """
        url = f"{self.agent_base_url}/internal/v1/perception/cameras/{status.camera_id}/status"
        payload = status.model_dump() if hasattr(status, "model_dump") else status.dict()
        try:
            resp = self.session.put(
                url,
                json=payload,
                headers=self._headers(),
                timeout=self.timeout,
            )
            return 200 <= resp.status_code < 300
        except Exception as exc:
            logger.warning(f"[Publisher] Status report failed for {status.camera_id}: {exc}")
            return False

    def fetch_camera_config(self, camera_id: str) -> Optional[CameraRunConfigContractV1]:
        """
        Fetches camera fence & run config via GET /internal/v1/perception/cameras/{camera_id}/config.
        """
        url = f"{self.agent_base_url}/internal/v1/perception/cameras/{camera_id}/config"
        try:
            resp = self.session.get(url, headers=self._headers(), timeout=self.timeout)
            if resp.status_code == 200:
                return CameraRunConfigContractV1(**resp.json())
            return None
        except Exception as exc:
            logger.warning(f"[Publisher] Fetch config failed for {camera_id}: {exc}")
            return None
