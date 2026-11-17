"""Locale definitions and HTTP Accept-Language parsing utilities."""
from __future__ import annotations

from typing import Literal

SupportedLocale = Literal["zh-CN", "zh-HK"]

DEFAULT_LOCALE: SupportedLocale = "zh-CN"

_LOCALE_TAG_MAP: tuple[tuple[tuple[str, ...], SupportedLocale], ...] = (
    (("zh-hk", "zh-tw", "zh-mo", "zh-hant"), "zh-HK"),
    (("zh-cn", "zh-sg", "zh-hans"), "zh-CN"),
)


def _normalize_tag(raw_tag: str) -> SupportedLocale | None:
    normalized = raw_tag.strip().lower().replace("_", "-")
    if not normalized:
        return None
    for prefixes, target in _LOCALE_TAG_MAP:
        if any(normalized == prefix or normalized.startswith(f"{prefix}-") for prefix in prefixes):
            return target
    return None


def parse_accept_language(header: str | None, *, fallback: SupportedLocale = DEFAULT_LOCALE) -> SupportedLocale:
    """Parse an HTTP Accept-Language header into a supported locale."""
    if not header or not header.strip():
        return fallback

    candidates: list[tuple[float, int, SupportedLocale]] = []
    for index, part in enumerate(header.split(",")):
        segment = part.strip()
        if not segment:
            continue
        pieces = [item.strip() for item in segment.split(";")]
        locale = _normalize_tag(pieces[0])
        if locale is None:
            continue
        quality = 1.0
        for param in pieces[1:]:
            if param.lower().startswith("q="):
                try:
                    quality = float(param[2:])
                except ValueError:
                    quality = 0.0
                break
        if quality > 0:
            candidates.append((quality, -index, locale))

    if not candidates:
        return fallback
    candidates.sort(reverse=True)
    return candidates[0][2]


def resolve_request_locale(
    accept_language: str | None = None,
    lang_param: str | None = None,
    *,
    fallback: SupportedLocale = DEFAULT_LOCALE,
) -> SupportedLocale:
    """Resolve effective request locale, prioritizing explicit query parameter over Accept-Language."""
    if lang_param:
        explicit = _normalize_tag(lang_param)
        if explicit is not None:
            return explicit
    return parse_accept_language(accept_language, fallback=fallback)
