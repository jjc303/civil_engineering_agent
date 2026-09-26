from __future__ import annotations

from collections.abc import Callable
from typing import Any


class ToolSpec:
    def __init__(self, description: str, parameters: str) -> None:
        self.description, self.parameters = description, parameters


class ToolRegistry:
    """Small explicit registry; adapters can expose the same tools to LangChain later."""

    def __init__(self) -> None:
        self._tools: dict[str, tuple[Callable[..., Any], ToolSpec]] = {}

    def register(self, name: str, handler: Callable[..., Any], *, description: str, parameters: str) -> None:
        if name in self._tools:
            raise ValueError(f"tool already registered: {name}")
        self._tools[name] = (handler, ToolSpec(description, parameters))

    def invoke(self, name: str, **kwargs: Any) -> Any:
        try:
            return self._tools[name][0](**kwargs)
        except KeyError as exc:
            raise ValueError(f"unknown tool: {name}") from exc

    @property
    def names(self) -> tuple[str, ...]:
        return tuple(self._tools)

    def catalog(self) -> list[dict[str, str]]:
        return [{"name": name, "description": spec.description, "parameters": spec.parameters} for name, (_, spec) in self._tools.items()]
