"""Add CV node registry and managed camera sources.

Revision ID: 20260926_0003
Revises: 20260925_0002
"""

from alembic import op
import sqlalchemy as sa


revision = "20260926_0003"
down_revision = "20260925_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cv_nodes",
        sa.Column("node_id", sa.String(length=128), primary_key=True),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("control_url", sa.String(length=1024), nullable=False),
        sa.Column("control_token_encrypted", sa.Text(), nullable=False),
        sa.Column("is_online", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("active_sessions", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("capacity", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_heartbeat_at_utc", sa.DateTime(timezone=True)),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at_utc", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_table(
        "managed_cameras",
        sa.Column("camera_id", sa.String(length=128), primary_key=True),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("node_id", sa.String(length=128), nullable=False),
        sa.Column("source_type", sa.String(length=16), nullable=False),
        sa.Column("source_uri_encrypted", sa.Text(), nullable=False),
        sa.Column("source_uri_masked", sa.String(length=1024), nullable=False),
        sa.Column("desired_state", sa.String(length=16), nullable=False, server_default="STOPPED"),
        sa.Column("monitor_session_id", sa.String(length=128)),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at_utc", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_managed_cameras_node_id", "managed_cameras", ["node_id"])


def downgrade() -> None:
    op.drop_index("ix_managed_cameras_node_id", table_name="managed_cameras")
    op.drop_table("managed_cameras")
    op.drop_table("cv_nodes")
