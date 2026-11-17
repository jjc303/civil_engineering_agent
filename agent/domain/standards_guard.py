"""Domain guard for verifying standard codes, titles, and clause references against retrieved evidence."""
from __future__ import annotations

import re
from collections.abc import Iterable

from agent.i18n import to_simplified_text

# Shared patterns for Chinese engineering standards, regulations, and clauses
_STANDARD_CODE_EXPR = (
    r"(?<![A-Za-z0-9])(?:GB/T|GB|JGJ/T|JGJ|JTG|CJJ|JG/T|DL/T|DL|SL|DB\d{0,2}(?:/T)?)"
    r"\s*(?:/T\s*)?\d{2,6}(?:[.-]\d+)*(?:-\d{4})?(?![A-Za-z0-9])"
)
_DECIMAL_CLAUSE_EXPR = r"第?\d+(?:\.\d+)+[条條]"
_CHINESE_OR_INT_CLAUSE_EXPR = r"第[一二三四五六七八九十百千零〇\d]+[条條]"
_CLAUSE_EXPR = f"{_DECIMAL_CLAUSE_EXPR}|{_CHINESE_OR_INT_CLAUSE_EXPR}"
_STRICT_BOOK_TITLE_EXPR = r"《[^》]{2,100}》"
_STANDARD_BOOK_TITLE_EXPR = (
    r"《[^》\n]{0,80}(?:规范|規範|标准|標準|规程|規程|导则|導則|图集|圖集|条例|條例|规定|規定|办法|辦法)[^》\n]{0,80}》"
)

_LIST_OR_DATA_SUFFIX_RE = re.compile(
    r"^\s*(?:[，,：:、；;。.\s]|(?:建议|建議|措施|违规|違規|记录|記錄|数据|數據|任务|任務|事件|告警|隐患|隱患|问题|問題|原因|要求是|内容|內容|情况|情況|通知|消息))"
)
_CITATION_PREFIX_RE = re.compile(
    r"(?:依据|依據|根据|根據|按照|参照|參照|遵照|违反|違反|符合|引用|规定|規定|条款|條款|》|[A-Za-z0-9])\s*$"
)
_CITATION_SUFFIX_RE = re.compile(
    r"^\s*(?:规定|規定|要求|明确|明確|指出|提出|执行|執行|办理|辦理|处罚|處罰)"
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
    if "." in raw or re.match(r"^\d+(?:\.\d+)+[条條]$", raw):
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
    """Normalize Chinese script, strip whitespace, and casefold for robust substring matching."""
    return re.sub(r"\s+", "", to_simplified_text(text)).casefold()


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

