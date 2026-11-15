"""Public notification link & route resolution without duplicated subpath prefixes (SRP)."""
from __future__ import annotations

from collections.abc import Mapping
from urllib.parse import urlencode, urlsplit

DEFAULT_WEB_BASE_URL = "http://127.0.0.1:5173"

DEFAULT_NOTIFICATION_ROUTES: dict[str, str] = {
    "dashboard": "/dashboard",
    "violations": "/violations",
    "rectification_tasks": "/rectification-tasks",
    "copilot": "/copilot",
    "learning": "/learning",
}


class NotificationLinkBuilder:
    """Resolves SPA action routes and API resource URLs against deployment base paths."""

    def __init__(
        self,
        web_base_url: str = DEFAULT_WEB_BASE_URL,
        *,
        app_base_path: str = "",
        routes: Mapping[str, str] | None = None,
    ) -> None:
        normalized_base = (web_base_url or DEFAULT_WEB_BASE_URL).strip().rstrip("/")
        parsed = urlsplit(normalized_base)
        self.origin = f"{parsed.scheme}://{parsed.netloc}" if parsed.scheme and parsed.netloc else ""
        base_path_from_url = parsed.path.rstrip("/")
        explicit_prefix = (app_base_path or "").strip().rstrip("/")
        if explicit_prefix and not explicit_prefix.startswith("/"):
            explicit_prefix = f"/{explicit_prefix}"
        self.base_path = base_path_from_url or explicit_prefix
        self.base_url = f"{self.origin}{self.base_path}" if self.origin else (self.base_path or DEFAULT_WEB_BASE_URL)
        self.routes: dict[str, str] = dict(DEFAULT_NOTIFICATION_ROUTES)
        if routes:
            for key, route in routes.items():
                clean = "/" + route.strip().lstrip("/")
                self.routes[key] = clean

    def route(self, route_key: str, **query: str | None) -> str:
        """Build an absolute SPA page URL for a configured route key."""
        path = self.routes.get(route_key)
        if path is None:
            path = "/" + route_key.strip().lstrip("/")
        url = self.resolve_path(path)
        filtered = {k: v for k, v in query.items() if v is not None and v != ""}
        if filtered:
            return f"{url}?{urlencode(filtered)}"
        return url

    def resolve_path(self, relative_or_prefixed_path: str) -> str:
        """Join a path to the deployment base without duplicating the subpath prefix."""
        clean = "/" + relative_or_prefixed_path.strip().lstrip("/")
        if self.base_path and (clean == self.base_path or clean.startswith(f"{self.base_path}/")):
            return f"{self.origin}{clean}" if self.origin else clean
        return f"{self.base_url.rstrip('/')}{clean}"

    def resolve_resource_url(self, url_or_path: str | None, *, fallback_route: str = "learning") -> str:
        """Resolve an absolute URL, prefixed API path, or unprefixed path into a valid link."""
        raw = (url_or_path or "").strip()
        if not raw:
            return self.route(fallback_route)
        lowered = raw.lower()
        if lowered.startswith(("http://", "https://")):
            return raw
        return self.resolve_path(raw)
