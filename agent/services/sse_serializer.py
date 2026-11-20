"""Shared Server-Sent Events (SSE) serialization helpers."""
from __future__ import annotations

import json
from typing import Any

from pydantic import BaseModel


def format_sse_event(event_type: str, data: Any) -> str:
    """Serialize a dict or Pydantic model into a standard SSE event frame."""
    payload = data.model_dump(mode="json") if isinstance(data, BaseModel) else data
    encoded = json.dumps(payload, ensure_ascii=False, default=str)
    return f"event: {event_type}\ndata: {encoded}\n\n"


def format_sse_comment(comment: str = "keepalive") -> str:
    """Return an SSE comment frame for connection keepalive."""
    return f": {comment}\n\n"
