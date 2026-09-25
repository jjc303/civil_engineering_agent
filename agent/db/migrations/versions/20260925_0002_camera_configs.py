"""Create versioned camera configuration table.

Revision ID: 20260925_0002
Revises: 20260925_0001
Create Date: 2026-09-25
"""

from alembic import op
import sqlalchemy as sa


revision = "20260925_0002"
down_revision = "20260925_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "camera_configs",
        sa.Column("camera_id", sa.String(length=128), nullable=False),
        sa.Column("config_version", sa.Integer(), nullable=False),
        sa.Column("source_width", sa.Integer(), nullable=False),
        sa.Column("source_height", sa.Integer(), nullable=False),
        sa.Column("enter_debounce_frames", sa.Integer(), nullable=False),
        sa.Column("exit_debounce_frames", sa.Integer(), nullable=False),
        sa.Column("helmet_debounce_frames", sa.Integer(), nullable=False),
        sa.Column("alarm_dwell_threshold_seconds", sa.Float(), nullable=False),
        sa.Column("zones", sa.JSON(), nullable=False),
        sa.Column("updated_at_utc", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("camera_id"),
    )


def downgrade() -> None:
    op.drop_table("camera_configs")
