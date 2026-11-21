"""Shared timezone normalization, request time-context formatting, and tool local-time enrichment."""
from __future__ import annotations

from collections.abc import Iterable, Sequence
from datetime import datetime, timezone
from typing import Any
from zoneinfo import ZoneInfo

DEFAULT_DISPLAY_TIMEZONE = "Asia/Shanghai"

WEEKDAY_ZH: tuple[str, ...] = (
    "星期一",
    "星期二",
    "星期三",
    "星期四",
    "星期五",
    "星期六",
    "星期日",
)


def normalize_to_utc(value: datetime | None) -> datetime | None:
    """Normalize any datetime to UTC; naive datetimes are treated as UTC for compatibility."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def resolve_zone_info(timezone_name: str | ZoneInfo | None = None) -> ZoneInfo:
    """Resolve a configured IANA timezone name or ZoneInfo instance."""
    if isinstance(timezone_name, ZoneInfo):
        return timezone_name
    key = (timezone_name or "").strip() or DEFAULT_DISPLAY_TIMEZONE
    return ZoneInfo(key)


def _zone_label(tz: ZoneInfo) -> str:
    return getattr(tz, "key", None) or str(tz)


def format_utc_offset(dt: datetime) -> str:
    """Format a datetime's UTC offset dynamically as e.g. 'UTC+08:00' or 'UTC-05:00'."""
    offset = dt.utcoffset()
    if offset is None:
        return "UTC+00:00"
    total_minutes = int(offset.total_seconds() // 60)
    sign = "+" if total_minutes >= 0 else "-"
    abs_minutes = abs(total_minutes)
    hours, minutes = divmod(abs_minutes, 60)
    return f"UTC{sign}{hours:02d}:{minutes:02d}"


def format_request_time_context(
    now_utc: datetime | None = None,
    timezone_name: str | ZoneInfo | None = None,
) -> str:
    """Render a minute-precision request time header for User Message injection."""
    base_utc = normalize_to_utc(now_utc) or datetime.now(timezone.utc)
    tz = resolve_zone_info(timezone_name)
    local_dt = base_utc.astimezone(tz)
    weekday = WEEKDAY_ZH[local_dt.weekday()]
    return (
        f"[当前时间] {local_dt.strftime('%Y-%m-%d %H:%M')} "
        f"({weekday}, {_zone_label(tz)}, {format_utc_offset(local_dt)})"
    )


def _to_local_datetime(
    value: datetime | str | None,
    timezone_name: str | ZoneInfo | None = None,
) -> tuple[datetime, ZoneInfo] | None:
    if value is None:
        return None
    if isinstance(value, str):
        raw = value.strip()
        if not raw:
            return None
        parsed = datetime.fromisoformat(raw.replace("Z", "+00:00"))
    else:
        parsed = value
    utc_dt = normalize_to_utc(parsed)
    if utc_dt is None:
        return None
    tz = resolve_zone_info(timezone_name)
    return utc_dt.astimezone(tz), tz


def format_local_datetime(
    value: datetime | str | None,
    timezone_name: str | ZoneInfo | None = None,
) -> str | None:
    """Convert a UTC datetime or ISO-8601 string into a human-readable local string with weekday."""
    try:
        resolved = _to_local_datetime(value, timezone_name)
    except ValueError:
        return value.strip() if isinstance(value, str) else None
    if resolved is None:
        return None
    local_dt, tz = resolved
    weekday = WEEKDAY_ZH[local_dt.weekday()]
    return f"{local_dt.strftime('%Y-%m-%d %H:%M:%S')} ({weekday}, {_zone_label(tz)})"


def format_local_time_short(
    value: datetime | str | None,
    timezone_name: str | ZoneInfo | None = None,
) -> str:
    """Format a UTC datetime into concise 'HH:MM (<IANA_TZ>)' local display."""
    try:
        resolved = _to_local_datetime(value, timezone_name)
    except ValueError:
        return "-"
    if resolved is None:
        return "-"
    local_dt, tz = resolved
    return f"{local_dt.strftime('%H:%M')} ({_zone_label(tz)})"


def enrich_record_local_times(
    record: dict[str, Any],
    field_pairs: Sequence[tuple[str, str]],
    timezone_name: str | ZoneInfo | None = None,
) -> dict[str, Any]:
    """Return a shallow copy of `record` enriched with `<field>_local` for present UTC fields."""
    enriched = dict(record)
    for utc_field, local_field in field_pairs:
        raw_val = enriched.get(utc_field)
        if raw_val is not None:
            formatted = format_local_datetime(raw_val, timezone_name)
            if formatted is not None:
                enriched[local_field] = formatted
    return enriched


def enrich_records_local_times(
    records: Iterable[dict[str, Any]],
    field_pairs: Sequence[tuple[str, str]],
    timezone_name: str | ZoneInfo | None = None,
) -> list[dict[str, Any]]:
    """Enrich an iterable of serialized tool records with formatted local timestamps."""
    return [enrich_record_local_times(item, field_pairs, timezone_name) for item in records]


def resolve_context_timezone(ctx: Any) -> ZoneInfo:
    """Resolve display timezone from ToolContext without hardcoding a provider or service."""
    extensions = getattr(ctx, "extensions", None)
    if isinstance(extensions, dict) and extensions.get("display_timezone"):
        return resolve_zone_info(extensions["display_timezone"])
    learning_service = getattr(ctx, "learning_service", None)
    learning_tz = getattr(learning_service, "display_timezone", None)
    if learning_tz is not None:
        return resolve_zone_info(learning_tz)
    return resolve_zone_info(DEFAULT_DISPLAY_TIMEZONE)
