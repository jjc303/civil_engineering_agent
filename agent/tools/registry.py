from __future__ import annotations

from collections.abc import Callable
from typing import Any


class ToolRegistry:
    """Small explicit registry; adapters can expose the same tools to LangChain later."""

    def __init__(self) -> None:
        self._tools: dict[str, Callable[..., Any]] = {}

    def register(self, name: str, handler: Callable[..., Any]) -> None:
        if name in self._tools:
            raise ValueError(f"tool already registered: {name}")
        self._tools[name] = handler

    def invoke(self, name: str, **kwargs: Any) -> Any:
        try:
            return self._tools[name](**kwargs)
        except KeyError as exc:
            raise ValueError(f"unknown tool: {name}") from exc

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self._tools)
