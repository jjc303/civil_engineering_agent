"""Learning center reports, document metadata and training.

Revision ID: 20261009_0010
Revises: 20261009_0009
"""
from alembic import op
import sqlalchemy as sa

revision = "20261009_0010"
down_revision = "20261009_0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("knowledge_documents", sa.Column("document_date", sa.DateTime(timezone=True)))
    op.add_column("knowledge_documents", sa.Column("source_display", sa.String(512)))
    op.add_column("knowledge_documents", sa.Column("risk_tags", sa.JSON(), nullable=True))
    op.execute("UPDATE knowledge_documents SET risk_tags = '[]' WHERE risk_tags IS NULL")
    with op.batch_alter_table("knowledge_documents") as batch:
        batch.alter_column("risk_tags", nullable=False, existing_type=sa.JSON())
    op.add_column("knowledge_documents", sa.Column("summary", sa.Text()))
    op.create_table("safety_reports",
        sa.Column("report_id", sa.String(36), primary_key=True),
        sa.Column("period_start_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("statistics_json", sa.JSON(), nullable=False),
        sa.Column("citations_json", sa.JSON(), nullable=False),
        sa.Column("content_json", sa.JSON(), nullable=False),
        sa.Column("pdf_path", sa.String(1024)),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("confirmed_at_utc", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_safety_reports_status", "safety_reports", ["status"])
    op.create_table("training_tasks",
        sa.Column("task_id", sa.String(36), primary_key=True),
        sa.Column("report_id", sa.String(36), sa.ForeignKey("safety_reports.report_id"), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("target_count", sa.Integer(), nullable=False),
        sa.Column("question_count", sa.Integer(), nullable=False),
        sa.Column("pass_score", sa.Integer(), nullable=False),
        sa.Column("selected_documents_json", sa.JSON(), nullable=False),
        sa.Column("material", sa.Text(), nullable=False),
        sa.Column("questions_json", sa.JSON(), nullable=False),
        sa.Column("access_token", sa.String(64), unique=True),
        sa.Column("created_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.Column("published_at_utc", sa.DateTime(timezone=True)),
    )
    op.create_index("ix_training_tasks_status", "training_tasks", ["status"])
    op.create_table("training_submissions",
        sa.Column("submission_id", sa.String(36), primary_key=True),
        sa.Column("task_id", sa.String(36), sa.ForeignKey("training_tasks.task_id"), nullable=False),
        sa.Column("worker_id", sa.String(64), nullable=False),
        sa.Column("worker_name", sa.String(128), nullable=False),
        sa.Column("answers_json", sa.JSON(), nullable=False),
        sa.Column("score", sa.Integer(), nullable=False),
        sa.Column("passed", sa.Boolean(), nullable=False),
        sa.Column("submitted_at_utc", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("task_id", "worker_id", name="uq_training_task_worker"),
    )
    op.create_index("ix_training_submissions_task_id", "training_submissions", ["task_id"])


def downgrade() -> None:
    op.drop_table("training_submissions")
    op.drop_table("training_tasks")
    op.drop_table("safety_reports")
    op.drop_column("knowledge_documents", "summary")
    op.drop_column("knowledge_documents", "risk_tags")
    op.drop_column("knowledge_documents", "document_date")
    op.drop_column("knowledge_documents", "source_display")
