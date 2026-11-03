from __future__ import annotations

import re
from pathlib import Path

from fastapi.testclient import TestClient

from agent.contracts.event_v1 import EventStatus, ViolationSeverity, ViolationType as AgentViolationType
from agent.core.config import Settings
from agent.domain.violation_catalog import (
    SEVERITY_LABELS,
    STATUS_LABELS,
    VIOLATION_LABELS,
    VIOLATION_RETRIEVAL_TERMS,
    VIOLATION_TYPES,
)
from agent.main import create_app
from perception.schemas.detection import ViolationType as PerceptionViolationType

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


def test_perception_and_agent_violation_enums_stay_in_sync() -> None:
    assert {item.value for item in AgentViolationType} == {item.value for item in PerceptionViolationType}
    assert set(VIOLATION_TYPES) == set(AgentViolationType)
    assert set(VIOLATION_LABELS) == {item.value for item in AgentViolationType}
    assert set(VIOLATION_RETRIEVAL_TERMS) == {item.value for item in AgentViolationType}


def test_meta_dictionaries_endpoint_exposes_canonical_labels() -> None:
    settings = Settings(
        database_url="sqlite+pysqlite:///:memory:",
        internal_perception_token="dict-test-token",
        llm_provider="fake",
        auto_create_schema=True,
    )
    with TestClient(create_app(settings)) as client:
        response = client.get("/api/v1/meta/dictionaries")
    assert response.status_code == 200
    body = response.json()
    assert body["violation_labels"] == VIOLATION_LABELS
    assert body["severity_labels"] == SEVERITY_LABELS
    assert body["status_labels"] == STATUS_LABELS
    assert {item["code"] for item in body["violation_types"]} == {item.value for item in AgentViolationType}
    assert set(body["severity_labels"]) == {item.value for item in ViolationSeverity}
    assert set(body["status_labels"]) == {item.value for item in EventStatus}


def _extract_ts_record(source: str, const_name: str) -> dict[str, str]:
    block_match = re.search(rf"export const {const_name}[^=]*=\s*\{{([^}}]+)\}}", source, re.S)
    assert block_match, f"missing {const_name} in dictionaries.ts"
    return dict(re.findall(r"(\w+)\s*:\s*'([^']+)'", block_match.group(1)))


def test_frontend_fallback_constants_match_backend_catalog() -> None:
    ts_path = PROJECT_ROOT / "web" / "src" / "constants" / "dictionaries.ts"
    source = ts_path.read_text(encoding="utf-8")
    assert _extract_ts_record(source, "DEFAULT_VIOLATION_LABELS") == VIOLATION_LABELS
    assert _extract_ts_record(source, "DEFAULT_SEVERITY_LABELS") == SEVERITY_LABELS
    assert _extract_ts_record(source, "DEFAULT_STATUS_LABELS") == STATUS_LABELS
