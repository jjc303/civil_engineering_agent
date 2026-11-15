"""Violation alert eligibility and throttling policy reusing shared ThrottlePort (SRP & DIP)."""
from __future__ import annotations

import logging

from agent.contracts.event_v1 import EventStatus
from agent.contracts.query import ViolationRecord
from agent.domain.violation_catalog import severity_rank
from agent.infra.cache import InMemoryThrottleAdapter
from agent.infra.ports import ThrottlePort

logger = logging.getLogger(__name__)


class FeishuAlertPolicy:
    """Determines whether a safety violation record should emit a Feishu alert."""

    def __init__(
        self,
        *,
        min_severity: str = "WARNING",
        cooldown_seconds: int = 60,
        throttle: ThrottlePort | None = None,
    ) -> None:
        self.min_severity = (min_severity or "WARNING").upper().strip()
        self.min_severity_rank = severity_rank(self.min_severity, default=2)
        self.throttle: ThrottlePort = (
            throttle if throttle is not None else InMemoryThrottleAdapter(cooldown_seconds=cooldown_seconds)
        )

    def evaluate(
        self,
        record: ViolationRecord,
        *,
        bypass_throttle: bool = False,
        escalated: bool = False,
    ) -> tuple[bool, str]:
        """Return (should_send, skip_reason)."""
        if record.status != EventStatus.ACTIVE.value:
            return False, f"violation status is {record.status}"

        if severity_rank(record.severity) < self.min_severity_rank:
            return False, f"severity {record.severity} below threshold {self.min_severity}"

        # Escalations (e.g. WARNING -> CRITICAL) penetrate the prior lower-severity cooldown.
        if bypass_throttle or escalated:
            return True, ""

        if not self.throttle.should_send(record.camera_id, record.violation_type, record.zone_id):
            logger.debug(
                "Skipped throttled Feishu violation alert (camera=%s, type=%s, zone=%s)",
                record.camera_id,
                record.violation_type,
                record.zone_id,
            )
            return False, "throttled within cooldown window"

        return True, ""
