"""Optional same-origin subpath deployment without changing CV callback URLs."""
from __future__ import annotations

import re
from starlette.responses import RedirectResponse
from starlette.types import ASGIApp, Receive, Scope, Send


def normalize_base_path(value: str) -> str:
    prefix = value.strip().rstrip("/")
    if prefix and not re.fullmatch(r"(?:/[A-Za-z0-9_-]+)+", prefix):
        raise ValueError("APP_BASE_PATH must be an absolute path such as /helmet")
    return prefix


class DeploymentPathMiddleware:
    def __init__(self, app: ASGIApp, prefix: str) -> None:
        self.app = app
        self.prefix = normalize_base_path(prefix)

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if self.prefix and scope["type"] in {"http", "websocket"}:
            path = scope["path"]
            if path == self.prefix and scope["type"] == "http":
                await RedirectResponse(self.prefix + "/", status_code=308)(scope, receive, send)
                return
            if path.startswith(self.prefix + "/"):
                # Match ASGI mount semantics: keep full path and extend root_path.
                scope = dict(scope, root_path=scope.get("root_path", "") + self.prefix)
            elif scope["type"] == "http" and (
                path in {"/", "/dashboard", "/violations", "/rectification-tasks",
                         "/zones", "/cameras", "/copilot", "/learning", "/demo", "/materials"}
                or path.startswith("/learn/")
            ):
                query = scope.get("query_string", b"").decode("ascii")
                target = self.prefix + path + (("?" + query) if query else "")
                await RedirectResponse(target, status_code=307)(scope, receive, send)
                return
        # Existing unprefixed internal endpoints remain available locally to CV.
        await self.app(scope, receive, send)
