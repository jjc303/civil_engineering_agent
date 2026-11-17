"""Response serialization presenter for decoupling canonical storage from locale display."""
from __future__ import annotations

from typing import Any, TypeVar

from pydantic import BaseModel

from .converter import DEFAULT_TEXT_CONVERTER, TextConverterPort
from .locale import SupportedLocale

T = TypeVar("T")

_SKIP_LOCALIZATION_KEYS: frozenset[str] = frozenset({
    "access_token",
    "action",
    "action_type",
    "camera_id",
    "chunk_id",
    "code",
    "confirmation_id",
    "conversation_id",
    "created_at_utc",
    "desired_state",
    "document_date",
    "document_id",
    "document_type",
    "due_at_utc",
    "error_code",
    "event_uuid",
    "expires_at_utc",
    "generated_at_utc",
    "job_id",
    "model_name",
    "model_version",
    "monitor_session_id",
    "node_id",
    "occurred_at_utc",
    "option_id",
    "pdf_url",
    "period_end_utc",
    "period_start_utc",
    "public_url",
    "qr_url",
    "report_id",
    "request_id",
    "resolved_at_utc",
    "risk_codes",
    "severity",
    "snapshot_uri",
    "source_type",
    "source_uri_masked",
    "status",
    "submitted_at_utc",
    "task_id",
    "tool_name",
    "training_id",
    "updated_at_utc",
    "validity_status",
    "violation_type",
    "worker_id",
    "zone_id",
})


def localize_response(
    payload: T,
    locale: SupportedLocale,
    *,
    converter: TextConverterPort = DEFAULT_TEXT_CONVERTER,
    skip_keys: frozenset[str] = _SKIP_LOCALIZATION_KEYS,
) -> T:
    """Project canonical response data into the requested locale without mutating inputs."""
    if locale == "zh-CN" or payload is None:
        return payload
    return _localize_value(payload, locale, converter=converter, skip_keys=skip_keys)


def _localize_value(
    value: Any,
    locale: SupportedLocale,
    *,
    converter: TextConverterPort,
    skip_keys: frozenset[str],
    field_name: str | None = None,
) -> Any:
    if field_name and field_name in skip_keys:
        return value
    if isinstance(value, str):
        return converter.to_locale(value, locale)
    if isinstance(value, BaseModel):
        updates: dict[str, Any] = {}
        for name in value.__class__.model_fields:
            if name in skip_keys:
                continue
            current = getattr(value, name)
            converted = _localize_value(
                current,
                locale,
                converter=converter,
                skip_keys=skip_keys,
                field_name=name,
            )
            if converted is not current:
                updates[name] = converted
        return value.model_copy(update=updates) if updates else value
    if isinstance(value, list):
        return [
            _localize_value(item, locale, converter=converter, skip_keys=skip_keys)
            for item in value
        ]
    if isinstance(value, tuple):
        return tuple(
            _localize_value(item, locale, converter=converter, skip_keys=skip_keys)
            for item in value
        )
    if isinstance(value, dict):
        return {
            key: (
                val
                if key in skip_keys
                else _localize_value(val, locale, converter=converter, skip_keys=skip_keys, field_name=str(key))
            )
            for key, val in value.items()
        }
    return value
