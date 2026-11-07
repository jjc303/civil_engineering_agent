"""Domain guard for verifying standard codes, titles, and clause references against retrieved evidence."""
from __future__ import annotations

import re
from collections.abc import Iterable

# Shared patterns for Chinese engineering standards, regulations, and clauses
_STANDARD_CODE_EXPR = (
    r"(?<![A-Za-z0-9])(?:GB/T|GB|JGJ/T|JGJ|JTG|CJJ|JG/T|DL/T|DL|SL|DB\d{0,2}(?:/T)?)"
    r"\s*(?:/T\s*)?\d{2,6}(?:[.-]\d+)*(?:-\d{4})?(?![A-Za-z0-9])"
)
_DECIMAL_CLAUSE_EXPR = r"第?\d+(?:\.\d+)+条"
_CHINESE_OR_INT_CLAUSE_EXPR = r"第[一二三四五六七八九十百千零〇\d]+条"
_CLAUSE_EXPR = f"{_DECIMAL_CLAUSE_EXPR}|{_CHINESE_OR_INT_CLAUSE_EXPR}"
_STRICT_BOOK_TITLE_EXPR = r"《[^》]{2,100}》"
_STANDARD_BOOK_TITLE_EXPR = r"《[^》\n]{0,80}(?:规范|标准|规程|导则|图集|条例|规定|办法)[^》\n]{0,80}》"

_LIST_OR_DATA_SUFFIX_RE = re.compile(
    r"^\s*(?:[，,：:、；;。.\s]|(?:建议|措施|违规|记录|数据|任务|事件|告警|隐患|问题|原因|要求是|内容|情况|通知|消息))"
)
_CITATION_PREFIX_RE = re.compile(
    r"(?:依据|根据|按照|参照|遵照|违反|符合|引用|规定|条款|》|[A-Za-z0-9])\s*$"
)
_CITATION_SUFFIX_RE = re.compile(
    r"^\s*(?:规定|要求|明确|指出|提出|执行|办理|处罚)"
)

STRICT_STANDARD_REFERENCE_RE = re.compile(
    f"{_STRICT_BOOK_TITLE_EXPR}|{_STANDARD_CODE_EXPR}|{_CLAUSE_EXPR}",
    re.IGNORECASE,
)

CHAT_STANDARD_REFERENCE_RE = re.compile(
    f"{_STANDARD_BOOK_TITLE_EXPR}|{_CLAUSE_EXPR}|{_STANDARD_CODE_EXPR}",
    re.IGNORECASE,
)


def _is_clause_citation(match: re.Match[str], text: str) -> bool:
    """Distinguish actual engineering standard clause citations from ordinal list/data items."""
    raw = match.group()
    if "." in raw or re.match(r"^\d+(?:\.\d+)+条$", raw):
        return True

    start, end = match.start(), match.end()
    prefix = text[max(0, start - 15) : start]
    suffix = text[end : min(len(text), end + 15)]

    has_cite_prefix = bool(_CITATION_PREFIX_RE.search(prefix))
    has_cite_suffix = bool(_CITATION_SUFFIX_RE.search(suffix))

    if _LIST_OR_DATA_SUFFIX_RE.search(suffix) and not has_cite_prefix:
        return False

    if has_cite_prefix or has_cite_suffix:
        return True

    return False


def normalize_evidence_text(text: str) -> str:
    """Strip whitespace and casefold for robust substring matching."""
    return re.sub(r"\s+", "", text).casefold()


def find_unsupported_standard_references(
    text: str,
    evidence_context: str,
    *,
    strict_book_titles: bool = False,
) -> list[str]:
    """Return all matched standard/clause references in `text` that are absent from `evidence_context`."""
    pattern = STRICT_STANDARD_REFERENCE_RE if strict_book_titles else CHAT_STANDARD_REFERENCE_RE
    normalized_source = normalize_evidence_text(evidence_context)
    unsupported: list[str] = []
    for match in pattern.finditer(text):
        raw_ref = match.group()
        # If match is a clause candidate, verify it is a real clause citation
        if re.match(rf"^(?:{_CLAUSE_EXPR})$", raw_ref) and not _is_clause_citation(match, text):
            continue

        cleaned_ref = raw_ref[1:-1] if raw_ref.startswith("《") and raw_ref.endswith("》") else raw_ref.strip("《》")
        if normalize_evidence_text(cleaned_ref) not in normalized_source:
            unsupported.append(raw_ref)
    return unsupported


def contains_unsupported_standard_reference(
    answer: str,
    standards_context: str,
    *,
    strict_book_titles: bool = False,
) -> bool:
    """Return True if `answer` cites any standard or clause not grounded in `standards_context`."""
    return bool(
        find_unsupported_standard_references(
            answer,
            standards_context,
            strict_book_titles=strict_book_titles,
        )
    )


def guard_standard_references(
    texts: Iterable[str],
    standards: Iterable[str],
    other_titles: Iterable[str] | None = None,
) -> None:
    """Raise ValueError if any text in `texts` cites a standard/title/clause absent from supplied evidence."""
    combined_evidence = "\n".join([*standards, *(other_titles or [])])
    for text in texts:
        unsupported = find_unsupported_standard_references(
            text,
            combined_evidence,
            strict_book_titles=True,
        )
        if unsupported:
            raise ValueError(f"generated text cites unsupported standard or clause: {unsupported[0]}")

