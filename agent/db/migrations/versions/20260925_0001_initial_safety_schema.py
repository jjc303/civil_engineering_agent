"""Create initial safety-event and camera-status tables.

Revision ID: 20260925_0001
Revises:
Create Date: 2026-09-25
"""

from alembic import op
import sqlalchemy as sa


revision = "20260925_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "violation_events",
        sa.Column("event_uuid", sa.String(length=36), nullable=False),
        sa.Column("schema_version", sa.String(length=16), nullable=False),
        sa.Column("camera_id", sa.String(length=128), nullable=False),
        sa.Column("monitor_session_id", sa.String(length=128), nullable=False),
        sa.Column("track_id", sa.BigInteger(), nullable=False),
        sa.Column("violation_type", sa.String(length=64), nullable=False),
        sa.Column("severity", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("zone_id", sa.String(length=128), nullable=True),
        sa.Column("zone_name", sa.String(length=255), nullable=True),
        sa.Column("occurred_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("resolved_at_utc", sa.DateTime(timezone=True), nullable=True),
        sa.Column("duration_seconds", sa.Numeric(precision=12, scale=3), nullable=False, server_default="0"),
        sa.Column("snapshot_uri", sa.String(length=1024), nullable=True),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("model_version", sa.String(length=128), nullable=True),
        sa.Column("extra_details", sa.JSON(), nullable=False),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at_utc", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.PrimaryKeyConstraint("event_uuid"),
    )
    op.create_index("ix_violation_events_camera_occurred", "violation_events", ["camera_id", "occurred_at_utc"])
    op.create_index("ix_violation_events_status_occurred", "violation_events", ["status", "occurred_at_utc"])
    op.create_index("ix_violation_events_severity_occurred", "violation_events", ["severity", "occurred_at_utc"])
    op.create_index("ix_violation_events_type_occurred", "violation_events", ["violation_type", "occurred_at_utc"])

    op.create_table(
        "camera_statuses",
        sa.Column("camera_id", sa.String(length=128), nullable=False),
        sa.Column("monitor_session_id", sa.String(length=128), nullable=False),
        sa.Column("is_online", sa.Boolean(), nullable=False),
        sa.Column("fps", sa.Float(), nullable=False),
        sa.Column("processed_frame_id", sa.BigInteger(), nullable=False),
        sa.Column("active_workers_count", sa.Integer(), nullable=False),
        sa.Column("model_name", sa.String(length=128), nullable=True),
        sa.Column("model_version", sa.String(length=128), nullable=True),
        sa.Column("reported_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("extra_details", sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint("camera_id"),
    )


def downgrade() -> None:
    op.drop_table("camera_statuses")
    op.drop_index("ix_violation_events_type_occurred", table_name="violation_events")
    op.drop_index("ix_violation_events_severity_occurred", table_name="violation_events")
    op.drop_index("ix_violation_events_status_occurred", table_name="violation_events")
    op.drop_index("ix_violation_events_camera_occurred", table_name="violation_events")
    op.drop_table("violation_events")
