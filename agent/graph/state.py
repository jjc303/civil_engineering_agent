from __future__ import annotations

from typing import Any, TypedDict


class SafetyGraphState(TypedDict, total=False):
    operation: str
    query: dict[str, Any]
    camera_id: str | None
    tool_name: str
    result: dict[str, Any]
    summary: str
