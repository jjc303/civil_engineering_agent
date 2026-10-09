"""Track standard validity explicitly instead of inferring it from filenames.

Revision ID: 20261009_0009
Revises: 20261009_0008
"""
from alembic import op
import sqlalchemy as sa

revision = "20261009_0009"
down_revision = "20261009_0008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("knowledge_documents", sa.Column("validity_status", sa.String(32), nullable=False, server_default="UNKNOWN"))


def downgrade() -> None:
    op.drop_column("knowledge_documents", "validity_status")
