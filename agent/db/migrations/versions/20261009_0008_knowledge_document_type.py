"""Separate standard documents from accident reports.

Revision ID: 20261009_0008
Revises: 20260927_0007
"""
from alembic import op
import sqlalchemy as sa

revision = "20261009_0008"
down_revision = "20260927_0007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("knowledge_documents", sa.Column("document_type", sa.String(32), nullable=False, server_default="ACCIDENT_REPORT"))
    op.create_index("ix_knowledge_documents_document_type", "knowledge_documents", ["document_type"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_documents_document_type", table_name="knowledge_documents")
    op.drop_column("knowledge_documents", "document_type")
