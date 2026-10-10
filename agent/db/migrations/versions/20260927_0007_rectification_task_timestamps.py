"""Align rectification task timestamp defaults with the ORM model.

Revision ID: 20260927_0007
Revises: 20260927_0006
"""
from alembic import op
import sqlalchemy as sa


revision = "20260927_0007"
down_revision = "20260927_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("rectification_tasks") as batch:
        for column in ("created_at_utc", "updated_at_utc"):
            batch.alter_column(column, existing_type=sa.DateTime(timezone=True),
                               existing_nullable=False, server_default=sa.text("CURRENT_TIMESTAMP"))


def downgrade() -> None:
    with op.batch_alter_table("rectification_tasks") as batch:
        for column in ("updated_at_utc", "created_at_utc"):
            batch.alter_column(column, existing_type=sa.DateTime(timezone=True), existing_nullable=False, server_default=None)
