"""Add confirmed agent write actions and rectification tasks.

Revision ID: 20260927_0006
Revises: 20260926_0005
"""
from alembic import op
import sqlalchemy as sa


revision = "20260927_0006"
down_revision = "20260926_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "rectification_tasks",
        sa.Column("task_id", sa.String(36), primary_key=True),
        sa.Column("event_uuid", sa.String(36), sa.ForeignKey("violation_events.event_uuid"), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("owner", sa.String(128), nullable=False),
        sa.Column("due_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("completed_at_utc", sa.DateTime(timezone=True)),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at_utc", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_rectification_tasks_event_uuid", "rectification_tasks", ["event_uuid"])
    op.create_index("ix_rectification_tasks_due_at_utc", "rectification_tasks", ["due_at_utc"])
    op.create_index("ix_rectification_tasks_status", "rectification_tasks", ["status"])
    op.create_table(
        "rectification_task_audits",
        sa.Column("audit_id", sa.String(36), primary_key=True),
        sa.Column("task_id", sa.String(36), sa.ForeignKey("rectification_tasks.task_id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("actor", sa.String(128), nullable=False),
        sa.Column("detail_safe_json", sa.JSON(), nullable=False),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_rectification_task_audits_task_id", "rectification_task_audits", ["task_id"])
    op.create_table(
        "agent_pending_actions",
        sa.Column("confirmation_id", sa.String(36), primary_key=True),
        sa.Column("conversation_id", sa.String(128), nullable=False),
        sa.Column("action_type", sa.String(64), nullable=False),
        sa.Column("summary", sa.String(512), nullable=False),
        sa.Column("payload_safe_json", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(32), nullable=False),
        sa.Column("expires_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("executed_at_utc", sa.DateTime(timezone=True)),
        sa.Column("result_safe_json", sa.JSON(), nullable=False),
        sa.Column("failure_detail_safe", sa.String(512)),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_agent_pending_actions_conversation_id", "agent_pending_actions", ["conversation_id"])
    op.create_index("ix_agent_pending_actions_status", "agent_pending_actions", ["status"])
    op.create_index("ix_agent_pending_actions_expires_at_utc", "agent_pending_actions", ["expires_at_utc"])
    op.create_table(
        "agent_pending_action_audits",
        sa.Column("audit_id", sa.String(36), primary_key=True),
        sa.Column("confirmation_id", sa.String(36), sa.ForeignKey("agent_pending_actions.confirmation_id", ondelete="CASCADE"), nullable=False),
        sa.Column("action", sa.String(64), nullable=False),
        sa.Column("actor", sa.String(128), nullable=False),
        sa.Column("detail_safe_json", sa.JSON(), nullable=False),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_agent_pending_action_audits_confirmation_id", "agent_pending_action_audits", ["confirmation_id"])


def downgrade() -> None:
    op.drop_index("ix_agent_pending_action_audits_confirmation_id", table_name="agent_pending_action_audits")
    op.drop_table("agent_pending_action_audits")
    op.drop_index("ix_agent_pending_actions_expires_at_utc", table_name="agent_pending_actions")
    op.drop_index("ix_agent_pending_actions_status", table_name="agent_pending_actions")
    op.drop_index("ix_agent_pending_actions_conversation_id", table_name="agent_pending_actions")
    op.drop_table("agent_pending_actions")
    op.drop_index("ix_rectification_task_audits_task_id", table_name="rectification_task_audits")
    op.drop_table("rectification_task_audits")
    op.drop_index("ix_rectification_tasks_status", table_name="rectification_tasks")
    op.drop_index("ix_rectification_tasks_due_at_utc", table_name="rectification_tasks")
    op.drop_index("ix_rectification_tasks_event_uuid", table_name="rectification_tasks")
    op.drop_table("rectification_tasks")
