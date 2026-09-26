"""Add data-driven Agent Copilot UI configuration.

Revision ID: 20260926_0005
Revises: 20260926_0004
"""
from alembic import op
import sqlalchemy as sa

revision = "20260926_0005"
down_revision = "20260926_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table("assistant_ui_configs", sa.Column("config_id", sa.String(64), primary_key=True), sa.Column("version", sa.Integer(), nullable=False), sa.Column("assistant_name", sa.String(128), nullable=False), sa.Column("welcome_message", sa.Text(), nullable=False), sa.Column("input_placeholder", sa.String(512), nullable=False), sa.Column("quick_questions", sa.JSON(), nullable=False), sa.Column("show_evidence", sa.Boolean(), nullable=False), sa.Column("updated_at_utc", sa.DateTime(timezone=True), nullable=False), sa.Column("updated_by", sa.String(128), nullable=False))
    op.create_table("assistant_ui_config_audits", sa.Column("audit_id", sa.String(36), primary_key=True), sa.Column("config_id", sa.String(64), nullable=False), sa.Column("version", sa.Integer(), nullable=False), sa.Column("actor", sa.String(128), nullable=False), sa.Column("detail_safe_json", sa.JSON(), nullable=False), sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False))
    op.create_index("ix_assistant_ui_config_audits_config_id", "assistant_ui_config_audits", ["config_id"])


def downgrade() -> None:
    op.drop_index("ix_assistant_ui_config_audits_config_id", table_name="assistant_ui_config_audits")
    op.drop_table("assistant_ui_config_audits")
    op.drop_table("assistant_ui_configs")
