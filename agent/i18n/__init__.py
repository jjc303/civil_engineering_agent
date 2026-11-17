"""Locale resolution, pure-script Chinese conversion, and response presentation."""
from __future__ import annotations

from .converter import DEFAULT_TEXT_CONVERTER, TextConverterPort, localize_text, to_simplified_text
from .locale import DEFAULT_LOCALE, SupportedLocale, parse_accept_language, resolve_request_locale
from .presenter import localize_response

__all__ = [
    "DEFAULT_LOCALE",
    "DEFAULT_TEXT_CONVERTER",
    "SupportedLocale",
    "TextConverterPort",
    "localize_response",
    "localize_text",
    "parse_accept_language",
    "resolve_request_locale",
    "to_simplified_text",
]
