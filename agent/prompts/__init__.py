from __future__ import annotations

from functools import lru_cache
from pathlib import Path
from string import Template
from typing import Any

from agent.contracts.chat import ToolDecision
from agent.contracts.event_v1 import EventStatus, ViolationSeverity, ViolationType
from agent.contracts.query import ViolationQuery

_PROMPT_DIR = Path(__file__).resolve().parent


@lru_cache(maxsize=32)
def _read_template(name: str) -> str:
    path = _PROMPT_DIR / f"{name}.md"
    if not path.is_file():
        raise FileNotFoundError(f"prompt template not found: {path}")
    return path.read_text(encoding="utf-8").strip()


def load_prompt(name: str, **variables: Any) -> str:
    raw = _read_template(name)
    if not variables:
        return raw
    return Template(raw).substitute(variables)


def render_decision_prompt() -> str:
    return load_prompt(
        "decision",
        decision_fields="、".join(ToolDecision.model_fields.keys()),
        query_fields="、".join(ViolationQuery.model_fields.keys()),
        severity_values="、".join(f'"{item.value}"' for item in ViolationSeverity),
        violation_type_values="、".join(f'"{item.value}"' for item in ViolationType),
        status_values="、".join(f'"{item.value}"' for item in EventStatus),
    )


__all__ = ["load_prompt", "render_decision_prompt"]
