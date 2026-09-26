from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from agent.contracts.chat import KnowledgeCitation, ToolResult, ToolTraceItem
from agent.db.models import (
    ConversationSessionModel, ConversationSummaryModel, ConversationToolAuditModel, ConversationTurnModel,
)


def _now() -> datetime:
    return datetime.now(timezone.utc)


class ConversationMemory:
    """Short-lived, minimized browser-session context stored in MySQL."""

    def __init__(self, session: Session, ttl_hours: int, recent_turns: int) -> None:
        self.session, self.ttl, self.recent_turns = session, timedelta(hours=ttl_hours), recent_turns

    def load_context(self, conversation_id: str | None) -> str:
        if not conversation_id:
            return ""
        session = self.session.get(ConversationSessionModel, conversation_id)
        now = _now()
        if not session or _as_utc(session.expires_at_utc) <= now:
            return ""
        summary = self.session.get(ConversationSummaryModel, conversation_id)
        turns = list(self.session.scalars(
            select(ConversationTurnModel).where(ConversationTurnModel.conversation_id == conversation_id)
            .order_by(ConversationTurnModel.sequence_no.desc()).limit(self.recent_turns)
        ))
        turns.reverse()
        parts = [summary.summary_text] if summary else []
        parts.extend(f"用户：{turn.user_text}\n助手：{turn.assistant_text}" for turn in turns)
        return "\n".join(parts)

    def persist(
        self, conversation_id: str | None, question: str, answer: str,
        results: list[ToolResult], trace: list[ToolTraceItem], citations: list[KnowledgeCitation],
    ) -> None:
        if not conversation_id:
            return
        now = _now()
        session = self.session.get(ConversationSessionModel, conversation_id)
        if not session or _as_utc(session.expires_at_utc) <= now:
            if session:
                self._delete_conversation(conversation_id)
            session = ConversationSessionModel(conversation_id=conversation_id, created_at_utc=now, last_active_at_utc=now, expires_at_utc=now + self.ttl)
            self.session.add(session)
            sequence = 1
        else:
            sequence = int(self.session.scalar(select(func.max(ConversationTurnModel.sequence_no)).where(ConversationTurnModel.conversation_id == conversation_id)) or 0) + 1
            session.last_active_at_utc, session.expires_at_utc = now, now + self.ttl
        turn_id = str(uuid4())
        facts = {"tools": [r.tool_name for r in results], "citations": [c.chunk_id for c in citations]}
        self.session.add(ConversationTurnModel(turn_id=turn_id, conversation_id=conversation_id, sequence_no=sequence, user_text=question, assistant_text=answer, verified_facts_json=facts, created_at_utc=now))
        # The audit row has a database foreign key to this turn.  SQLAlchemy
        # has no ORM relationship here to infer ordering, so flush explicitly
        # before inserting audit rows (required by MySQL's FK enforcement).
        self.session.flush()
        summary = self.session.get(ConversationSummaryModel, conversation_id)
        summary_text = _safe_summary(question, answer, citations)
        if summary:
            summary.summary_text, summary.covered_through_seq, summary.updated_at_utc = summary_text, sequence, now
        else:
            self.session.add(ConversationSummaryModel(conversation_id=conversation_id, summary_text=summary_text, covered_through_seq=sequence, updated_at_utc=now))
        for item in trace:
            self.session.add(ConversationToolAuditModel(audit_id=str(uuid4()), conversation_id=conversation_id, turn_id=turn_id, tool_name=item.tool_name, success=item.success, duration_ms=item.duration_ms, purpose=item.purpose, created_at_utc=now))

    def cleanup_expired(self) -> int:
        expired = list(self.session.scalars(select(ConversationSessionModel.conversation_id).where(ConversationSessionModel.expires_at_utc <= _now())))
        for conversation_id in expired:
            self._delete_conversation(conversation_id)
        return len(expired)

    def _delete_conversation(self, conversation_id: str) -> None:
        turn_ids = select(ConversationTurnModel.turn_id).where(ConversationTurnModel.conversation_id == conversation_id)
        self.session.execute(delete(ConversationToolAuditModel).where(ConversationToolAuditModel.conversation_id == conversation_id))
        self.session.execute(delete(ConversationSummaryModel).where(ConversationSummaryModel.conversation_id == conversation_id))
        self.session.execute(delete(ConversationTurnModel).where(ConversationTurnModel.conversation_id == conversation_id))
        self.session.execute(delete(ConversationSessionModel).where(ConversationSessionModel.conversation_id == conversation_id))


def _safe_summary(question: str, answer: str, citations: list[KnowledgeCitation]) -> str:
    # Bounded plaintext only; credentials/connection strings are never constructed here.
    text = f"最近问题：{question[:500]}\n已验证回答：{answer[:1000]}"
    if citations:
        text += "\n资料：" + ", ".join(f"{c.title} v{c.version_no}" for c in citations[:4])
    return text


def _as_utc(value: datetime) -> datetime:
    return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
