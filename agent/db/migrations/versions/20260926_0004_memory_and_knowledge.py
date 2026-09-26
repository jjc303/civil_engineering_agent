"""Add short-lived conversation memory and versioned knowledge metadata.

Revision ID: 20260926_0004
Revises: 20260926_0003
"""

from alembic import op
import sqlalchemy as sa

revision = "20260926_0004"
down_revision = "20260926_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("conversation_sessions", sa.Column("conversation_id", sa.String(128), primary_key=True), sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False), sa.Column("last_active_at_utc", sa.DateTime(timezone=True), nullable=False), sa.Column("expires_at_utc", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_conversation_sessions_expires_at_utc", "conversation_sessions", ["expires_at_utc"])
    op.create_table("conversation_turns", sa.Column("turn_id", sa.String(36), primary_key=True), sa.Column("conversation_id", sa.String(128), sa.ForeignKey("conversation_sessions.conversation_id", ondelete="CASCADE"), nullable=False), sa.Column("sequence_no", sa.Integer(), nullable=False), sa.Column("user_text", sa.Text(), nullable=False), sa.Column("assistant_text", sa.Text(), nullable=False), sa.Column("verified_facts_json", sa.JSON(), nullable=False), sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False), sa.UniqueConstraint("conversation_id", "sequence_no", name="uq_conversation_turn_sequence"))
    op.create_index("ix_conversation_turns_conversation_id", "conversation_turns", ["conversation_id"])
    op.create_table("conversation_summaries", sa.Column("conversation_id", sa.String(128), sa.ForeignKey("conversation_sessions.conversation_id", ondelete="CASCADE"), primary_key=True), sa.Column("summary_text", sa.Text(), nullable=False), sa.Column("covered_through_seq", sa.Integer(), nullable=False), sa.Column("updated_at_utc", sa.DateTime(timezone=True), nullable=False))
    op.create_table("conversation_tool_audits", sa.Column("audit_id", sa.String(36), primary_key=True), sa.Column("conversation_id", sa.String(128), sa.ForeignKey("conversation_sessions.conversation_id", ondelete="CASCADE"), nullable=False), sa.Column("turn_id", sa.String(36), sa.ForeignKey("conversation_turns.turn_id", ondelete="SET NULL")), sa.Column("tool_name", sa.String(64), nullable=False), sa.Column("success", sa.Boolean(), nullable=False), sa.Column("duration_ms", sa.Integer(), nullable=False), sa.Column("purpose", sa.String(256), nullable=False), sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_conversation_tool_audits_conversation_id", "conversation_tool_audits", ["conversation_id"])
    op.create_table("knowledge_documents", sa.Column("document_id", sa.String(36), primary_key=True), sa.Column("title", sa.String(255), nullable=False), sa.Column("source_label", sa.String(512), nullable=False), sa.Column("checksum_sha256", sa.String(64), nullable=False, unique=True), sa.Column("current_version", sa.Integer(), nullable=False), sa.Column("status", sa.String(32), nullable=False), sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False), sa.Column("created_by", sa.String(128), nullable=False), sa.Column("retired_at_utc", sa.DateTime(timezone=True)))
    op.create_index("ix_knowledge_documents_status", "knowledge_documents", ["status"])
    op.create_table("knowledge_document_versions", sa.Column("document_version_id", sa.String(36), primary_key=True), sa.Column("document_id", sa.String(36), sa.ForeignKey("knowledge_documents.document_id"), nullable=False), sa.Column("version_no", sa.Integer(), nullable=False), sa.Column("storage_key", sa.String(1024), nullable=False), sa.Column("checksum_sha256", sa.String(64), nullable=False, unique=True), sa.Column("status", sa.String(32), nullable=False), sa.Column("parser_name", sa.String(128)), sa.Column("page_count", sa.Integer()), sa.Column("indexed_at_utc", sa.DateTime(timezone=True)), sa.Column("retired_at_utc", sa.DateTime(timezone=True)), sa.Column("failure_code", sa.String(64)), sa.Column("failure_detail_safe", sa.String(512)), sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False), sa.Column("created_by", sa.String(128), nullable=False), sa.UniqueConstraint("document_id", "version_no", name="uq_knowledge_document_version"))
    op.create_index("ix_knowledge_document_versions_document_id", "knowledge_document_versions", ["document_id"]); op.create_index("ix_knowledge_document_versions_status", "knowledge_document_versions", ["status"])
    op.create_table("knowledge_index_jobs", sa.Column("job_id", sa.String(36), primary_key=True), sa.Column("document_version_id", sa.String(36), sa.ForeignKey("knowledge_document_versions.document_version_id"), nullable=False), sa.Column("operation", sa.String(32), nullable=False), sa.Column("status", sa.String(32), nullable=False), sa.Column("attempt_count", sa.Integer(), nullable=False), sa.Column("started_at_utc", sa.DateTime(timezone=True)), sa.Column("finished_at_utc", sa.DateTime(timezone=True)), sa.Column("error_code", sa.String(64)), sa.Column("error_detail_safe", sa.String(512)), sa.Column("requested_by", sa.String(128), nullable=False), sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_knowledge_index_jobs_document_version_id", "knowledge_index_jobs", ["document_version_id"]); op.create_index("ix_knowledge_index_jobs_status", "knowledge_index_jobs", ["status"])
    op.create_table("knowledge_audits", sa.Column("audit_id", sa.String(36), primary_key=True), sa.Column("actor", sa.String(128), nullable=False), sa.Column("action", sa.String(64), nullable=False), sa.Column("document_id", sa.String(36)), sa.Column("document_version_id", sa.String(36)), sa.Column("job_id", sa.String(36)), sa.Column("detail_safe_json", sa.JSON(), nullable=False), sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_knowledge_audits_document_id", "knowledge_audits", ["document_id"])


def downgrade() -> None:
    for table in ("knowledge_audits", "knowledge_index_jobs", "knowledge_document_versions", "knowledge_documents", "conversation_tool_audits", "conversation_summaries", "conversation_turns", "conversation_sessions"):
        op.drop_table(table)
