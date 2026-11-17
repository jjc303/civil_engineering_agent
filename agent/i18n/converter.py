"""Text script converter abstraction and zhconv adapter (DIP + Adapter Pattern)."""
from __future__ import annotations

import re
from typing import Protocol

import zhconv

from .locale import SupportedLocale

_PROTECTED_SEGMENT_RE = re.compile(
    r"(```[\s\S]*?```|`[^`\n]+`|https?://[^\s<>()\"']+)",
)
_HAS_CJK_RE = re.compile(r"[\u4e00-\u9fff]")

_LOCALE_TARGET_MAP: dict[SupportedLocale, str] = {
    "zh-CN": "zh-cn",
    "zh-HK": "zh-hk",
}


class TextConverterPort(Protocol):
    """Abstract port for Chinese script conversion."""

    def to_locale(self, text: str, locale: SupportedLocale) -> str:
        """Convert text to the target locale's Chinese script while preserving code/URLs."""

    def to_simplified(self, text: str) -> str:
        """Normalize Chinese text to canonical Simplified Chinese."""


class ZhconvTextConverter:
    """zhconv-backed adapter protecting Markdown code spans and URLs."""

    def to_locale(self, text: str, locale: SupportedLocale) -> str:
        if not text or locale == "zh-CN" or not _HAS_CJK_RE.search(text):
            return text
        target = _LOCALE_TARGET_MAP[locale]
        return self._convert_preserving_protected(text, target)

    def to_simplified(self, text: str) -> str:
        if not text or not _HAS_CJK_RE.search(text):
            return text
        return self._convert_preserving_protected(text, "zh-cn")

    @staticmethod
    def _convert_preserving_protected(text: str, target: str) -> str:
        parts = _PROTECTED_SEGMENT_RE.split(text)
        if len(parts) == 1:
            return zhconv.convert(text, target)
        return "".join(
            part if index % 2 == 1 else zhconv.convert(part, target)
            for index, part in enumerate(parts)
        )


DEFAULT_TEXT_CONVERTER: TextConverterPort = ZhconvTextConverter()


def localize_text(
    text: str,
    locale: SupportedLocale,
    *,
    converter: TextConverterPort = DEFAULT_TEXT_CONVERTER,
) -> str:
    """Convert text to the requested locale without mutating non-CJK or protected spans."""
    return converter.to_locale(text, locale)


def to_simplified_text(
    text: str,
    *,
    converter: TextConverterPort = DEFAULT_TEXT_CONVERTER,
) -> str:
    """Normalize text to canonical Simplified Chinese for storage and search matching."""
    return converter.to_simplified(text)
