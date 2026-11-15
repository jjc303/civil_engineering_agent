from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from agent.contracts.event_v1 import EventStatus, ViolationSeverity, ViolationType


@dataclass(frozen=True)
class ViolationTypeInfo:
    code: ViolationType
    label: str
    retrieval_term: str
    standard_hint: str


DEFAULT_STANDARD_HINT = (
    "📖 **《建筑施工安全检查标准》JGJ 59-2011**\n"
    "请现场安全员立即核实现场作业环境并督促整改。"
)

VIOLATION_TYPES: dict[ViolationType, ViolationTypeInfo] = {
    ViolationType.NO_HELMET: ViolationTypeInfo(
        code=ViolationType.NO_HELMET,
        label="未佩戴安全帽",
        retrieval_term="安全帽未规范佩戴",
        standard_hint=(
            "📖 **《建筑施工高处作业安全技术规范》JGJ 80-2016 第 3.0.5 条**\n"
            "进入施工现场的人员必须正确佩戴符合国家标准的安全帽，系好下颏带。"
        ),
    ),
    ViolationType.DANGER_ZONE_INTRUSION: ViolationTypeInfo(
        code=ViolationType.DANGER_ZONE_INTRUSION,
        label="危险区域入侵",
        retrieval_term="危险区域进入",
        standard_hint=(
            "📖 **《建筑机械使用安全技术规程》JGJ 33-2012 第 2.0.15 条**\n"
            "起重吊装及高危机械回转半径禁行区域内，严禁非作业人员擅自进入或穿行。"
        ),
    ),
    ViolationType.DWELL_TIMEOUT: ViolationTypeInfo(
        code=ViolationType.DWELL_TIMEOUT,
        label="危险区域停留超时",
        retrieval_term="危险区域停留超时",
        standard_hint=(
            "📖 **《建筑施工安全检查标准》JGJ 59-2011 第 3.1.3 条**\n"
            "高风险受限及临边危险区域严禁人员长时间滞留，须立即组织现场疏导与核查。"
        ),
    ),
}

VIOLATION_LABELS: dict[str, str] = {
    info.code.value: info.label for info in VIOLATION_TYPES.values()
}

VIOLATION_RETRIEVAL_TERMS: dict[str, str] = {
    info.code.value: info.retrieval_term for info in VIOLATION_TYPES.values()
}

VIOLATION_STANDARD_HINTS: dict[str, str] = {
    info.code.value: info.standard_hint for info in VIOLATION_TYPES.values()
}

SEVERITY_RANK: dict[str, int] = {
    ViolationSeverity.INFO.value: 1,
    ViolationSeverity.WARNING.value: 2,
    ViolationSeverity.CRITICAL.value: 3,
}

SEVERITY_LABELS: dict[str, str] = {
    ViolationSeverity.CRITICAL.value: "严重",
    ViolationSeverity.WARNING.value: "警告",
    ViolationSeverity.INFO.value: "提示",
}

SEVERITY_DETAILED_LABELS: dict[str, str] = {
    ViolationSeverity.CRITICAL.value: "严重告警 (CRITICAL)",
    ViolationSeverity.WARNING.value: "风险预警 (WARNING)",
    ViolationSeverity.INFO.value: "一般提示 (INFO)",
}

STATUS_LABELS: dict[str, str] = {
    EventStatus.ACTIVE.value: "待关注",
    EventStatus.RESOLVED.value: "已解除",
    EventStatus.FALSE_ALARM.value: "误报",
}


def severity_rank(severity: str | ViolationSeverity | None, default: int = 1) -> int:
    """Return numeric rank for a severity value."""
    if severity is None:
        return 0
    key = severity.value if isinstance(severity, ViolationSeverity) else str(severity).upper().strip()
    return SEVERITY_RANK.get(key, default)


def get_standard_hint(
    violation_type: str,
    overrides: Mapping[str, str] | None = None,
) -> str:
    """Resolve regulatory guidance hint with optional configuration overrides."""
    if overrides and violation_type in overrides and overrides[violation_type].strip():
        return overrides[violation_type].strip()
    return VIOLATION_STANDARD_HINTS.get(violation_type, DEFAULT_STANDARD_HINT)


def should_notify_violation_change(
    *,
    operation: str,
    previous_status: str | None,
    previous_severity: str | None,
    current_status: str,
    current_severity: str,
) -> tuple[bool, bool]:
    """Determine whether an event upsert warrants a notification and whether it escalated.

    Returns (should_notify, is_escalation).
    """
    if current_status != EventStatus.ACTIVE.value:
        return False, False
    if operation == "CREATED" or previous_status != EventStatus.ACTIVE.value:
        return True, False
    escalated = severity_rank(current_severity) > severity_rank(previous_severity, default=0)
    return escalated, escalated


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
