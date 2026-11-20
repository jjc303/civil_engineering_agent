"""Shared standards retrieval and context formatting service (DRY)."""
from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import TYPE_CHECKING

from agent.contracts.chat import KnowledgeCitation
from agent.prompts.chat_messages import (
    STANDARDS_EMPTY_CONTEXT,
    STANDARDS_FRAGMENT_TEMPLATE,
    STANDARDS_RETRIEVAL_FAILED_CONTEXT,
)

if TYPE_CHECKING:
    from agent.services.knowledge_service import KnowledgeService

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class StandardsContextResult:
    """Result of automatic standards RAG retrieval for a user question."""

    context_text: str
    citations: list[KnowledgeCitation] = field(default_factory=list)
    error_code: str | None = None


def build_standards_context(
    knowledge_service: "KnowledgeService | None",
    question: str,
    top_k: int,
    *,
    failure_log_message: str = "Standards retrieval failed",
) -> StandardsContextResult:
    """Retrieve relevant standards fragments and format them uniformly."""
    if knowledge_service is None:
        return StandardsContextResult(context_text=STANDARDS_EMPTY_CONTEXT)

    try:
        fragments, citations = knowledge_service.search_standards(question, top_k)
        if not fragments:
            return StandardsContextResult(
                context_text=STANDARDS_EMPTY_CONTEXT,
                citations=list(citations),
            )
        formatted = "\n\n".join(
            STANDARDS_FRAGMENT_TEMPLATE.format(
                title=item["title"],
                page_or_section=item["page_or_section"],
                source_label=item["source_label"],
                validity_status=item["validity_status"],
                content=item["content"],
            )
            for item in fragments
        )
        return StandardsContextResult(
            context_text=formatted,
            citations=list(citations),
        )
    except Exception:
        logger.exception(failure_log_message)
        return StandardsContextResult(
            context_text=STANDARDS_RETRIEVAL_FAILED_CONTEXT,
            error_code="STANDARDS_RETRIEVAL_FAILED",
        )
