from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from agent.contracts.event_v1 import EventStatus, ViolationSeverity, ViolationType


@dataclass(frozen=True)
class ViolationTypeInfo:
    code: ViolationType
    label: str
    retrieval_term: str


VIOLATION_TYPES: dict[ViolationType, ViolationTypeInfo] = {
    ViolationType.NO_HELMET: ViolationTypeInfo(
        code=ViolationType.NO_HELMET,
        label="未佩戴安全帽",
        retrieval_term="安全帽未规范佩戴",
    ),
    ViolationType.DANGER_ZONE_INTRUSION: ViolationTypeInfo(
        code=ViolationType.DANGER_ZONE_INTRUSION,
        label="危险区域入侵",
        retrieval_term="危险区域进入",
    ),
    ViolationType.DWELL_TIMEOUT: ViolationTypeInfo(
        code=ViolationType.DWELL_TIMEOUT,
        label="危险区域停留超时",
        retrieval_term="危险区域停留超时",
    ),
}

VIOLATION_LABELS: dict[str, str] = {
    info.code.value: info.label for info in VIOLATION_TYPES.values()
}

VIOLATION_RETRIEVAL_TERMS: dict[str, str] = {
    info.code.value: info.retrieval_term for info in VIOLATION_TYPES.values()
}

SEVERITY_LABELS: dict[str, str] = {
    ViolationSeverity.CRITICAL.value: "严重",
    ViolationSeverity.WARNING.value: "警告",
    ViolationSeverity.INFO.value: "提示",
}

STATUS_LABELS: dict[str, str] = {
    EventStatus.ACTIVE.value: "待关注",
    EventStatus.RESOLVED.value: "已解除",
    EventStatus.FALSE_ALARM.value: "误报",
}


def dictionaries_payload() -> dict[str, Any]:
    return {
        "violation_types": [
            {"code": info.code.value, "label": info.label}
            for info in VIOLATION_TYPES.values()
        ],
        "violation_labels": dict(VIOLATION_LABELS),
        "severity_labels": dict(SEVERITY_LABELS),
        "status_labels": dict(STATUS_LABELS),
    }
