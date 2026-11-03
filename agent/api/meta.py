from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from agent.domain.violation_catalog import dictionaries_payload

router = APIRouter(prefix="/api/v1/meta", tags=["meta"])


@router.get("/dictionaries")
def get_dictionaries() -> dict[str, Any]:
    return dictionaries_payload()
