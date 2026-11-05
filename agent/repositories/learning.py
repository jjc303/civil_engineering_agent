"""Repository encapsulating persistence and aggregation queries for the learning domain."""
from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.orm import Session

from agent.db.models import (
    KnowledgeDocumentModel,
    SafetyReportModel,
    TrainingSubmissionModel,
    TrainingTaskModel,
    ViolationEventModel,
)


class LearningRepository:
    """Data access layer for safety reports, worker training tasks, submissions, and risk aggregations."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def aggregate_period_violations(
        self,
        period_start_utc: datetime,
        period_end_utc: datetime,
    ) -> dict[str, Any]:
        conditions = (
            ViolationEventModel.occurred_at_utc >= period_start_utc,
            ViolationEventModel.occurred_at_utc < period_end_utc,
            ViolationEventModel.status != "FALSE_ALARM",
        )
        total = int(
            self.session.scalar(
                select(func.count()).select_from(ViolationEventModel).where(*conditions)
            )
            or 0
        )
        by_type = dict(
            self.session.execute(
                select(ViolationEventModel.violation_type, func.count())
                .where(*conditions)
                .group_by(ViolationEventModel.violation_type)
            ).all()
        )
        by_severity = dict(
            self.session.execute(
                select(ViolationEventModel.severity, func.count())
                .where(*conditions)
                .group_by(ViolationEventModel.severity)
            ).all()
        )
        zones = self.session.execute(
            select(ViolationEventModel.zone_name, func.count())
            .where(*conditions)
            .group_by(ViolationEventModel.zone_name)
        ).all()
        groups = self.session.execute(
            select(
                ViolationEventModel.camera_id,
                ViolationEventModel.zone_id,
                ViolationEventModel.violation_type,
                func.count(),
            )
            .where(*conditions)
            .group_by(
                ViolationEventModel.camera_id,
                ViolationEventModel.zone_id,
                ViolationEventModel.violation_type,
            )
        ).all()
        return {
            "total": total,
            "by_type": by_type,
            "by_severity": by_severity,
            "by_zone": {name or "未标注区域": count for name, count in zones},
            "repeat_occurrences": sum(max(0, count - 1) for *_, count in groups),
            "repeat_groups": sorted(
                (
                    {
                        "camera_id": cam,
                        "zone_id": zone,
                        "violation_type": kind,
                        "count": count,
                    }
                    for cam, zone, kind, count in groups
                    if count > 1
                ),
                key=lambda item: item["count"],
                reverse=True,
            )[:20],
            "excluded_status": "FALSE_ALARM",
            "end_exclusive": True,
        }

    def add_report(self, report: SafetyReportModel) -> SafetyReportModel:
        self.session.add(report)
        self.session.flush()
        return report

    def list_reports(self, limit: int = 100) -> list[SafetyReportModel]:
        return list(
            self.session.scalars(
                select(SafetyReportModel)
                .order_by(SafetyReportModel.created_at_utc.desc())
                .limit(limit)
            )
        )

    def get_report(self, report_id: str) -> SafetyReportModel | None:
        return self.session.get(SafetyReportModel, report_id)

    def has_training_for_report(self, report_id: str) -> bool:
        return bool(
            self.session.scalar(
                select(TrainingTaskModel.task_id)
                .where(TrainingTaskModel.report_id == report_id)
                .limit(1)
            )
        )

    def delete_report(self, report: SafetyReportModel) -> None:
        self.session.delete(report)

    def aggregate_weekly_overview(
        self,
        week_start: datetime,
        now: datetime,
    ) -> tuple[list[tuple[str, str, int]], list[TrainingTaskModel], dict[str, dict[str, Any]]]:
        conditions = (
            ViolationEventModel.occurred_at_utc >= week_start,
            ViolationEventModel.occurred_at_utc < now,
            ViolationEventModel.status != "FALSE_ALARM",
        )
        risk_rows = list(
            self.session.execute(
                select(
                    ViolationEventModel.violation_type,
                    ViolationEventModel.severity,
                    func.count(),
                )
                .where(*conditions)
                .group_by(ViolationEventModel.violation_type, ViolationEventModel.severity)
            ).all()
        )
        weekly_tasks = list(
            self.session.scalars(
                select(TrainingTaskModel).where(
                    TrainingTaskModel.created_at_utc >= week_start,
                    TrainingTaskModel.created_at_utc < now,
                )
            )
        )
        published_ids = [task.task_id for task in weekly_tasks if task.status == "PUBLISHED"]
        completion_rows = (
            self.session.execute(
                select(
                    TrainingSubmissionModel.task_id,
                    func.count(),
                    func.avg(TrainingSubmissionModel.score),
                )
                .where(TrainingSubmissionModel.task_id.in_(published_ids))
                .group_by(TrainingSubmissionModel.task_id)
            ).all()
            if published_ids
            else []
        )
        completions = {
            task_id: {"count": count, "average_score": round(float(average or 0), 1)}
            for task_id, count, average in completion_rows
        }
        return risk_rows, weekly_tasks, completions

    def get_active_accident_reports_by_ids(
        self,
        document_ids: list[str],
    ) -> dict[str, KnowledgeDocumentModel]:
        if not document_ids:
            return {}
        rows = self.session.scalars(
            select(KnowledgeDocumentModel).where(
                KnowledgeDocumentModel.document_id.in_(document_ids),
                KnowledgeDocumentModel.status == "ACTIVE",
                KnowledgeDocumentModel.document_type == "ACCIDENT_REPORT",
            )
        )
        return {row.document_id: row for row in rows}

    def query_active_documents(
        self,
        document_type: str | None = None,
        date_start: datetime | None = None,
        date_end: datetime | None = None,
    ) -> list[KnowledgeDocumentModel]:
        stmt = select(KnowledgeDocumentModel).where(KnowledgeDocumentModel.status == "ACTIVE")
        if document_type:
            stmt = stmt.where(KnowledgeDocumentModel.document_type == document_type)
        if date_start:
            stmt = stmt.where(KnowledgeDocumentModel.document_date >= date_start)
        if date_end:
            stmt = stmt.where(KnowledgeDocumentModel.document_date < date_end)
        return list(
            self.session.scalars(stmt.order_by(KnowledgeDocumentModel.created_at_utc.desc()))
        )

    def add_training_task(self, task: TrainingTaskModel) -> TrainingTaskModel:
        self.session.add(task)
        self.session.flush()
        return task

    def list_training_tasks(self, limit: int = 100) -> list[TrainingTaskModel]:
        return list(
            self.session.scalars(
                select(TrainingTaskModel)
                .order_by(TrainingTaskModel.created_at_utc.desc())
                .limit(limit)
            )
        )

    def get_training_task(self, task_id: str) -> TrainingTaskModel | None:
        return self.session.get(TrainingTaskModel, task_id)

    def get_published_training_by_token(self, token: str) -> TrainingTaskModel | None:
        return self.session.scalar(
            select(TrainingTaskModel).where(
                TrainingTaskModel.access_token == token,
                TrainingTaskModel.status == "PUBLISHED",
            )
        )

    def delete_training_task(self, task: TrainingTaskModel) -> None:
        self.session.execute(
            delete(TrainingSubmissionModel).where(
                TrainingSubmissionModel.task_id == task.task_id
            )
        )
        self.session.delete(task)

    def has_worker_submitted(self, task_id: str, worker_id: str) -> bool:
        return bool(
            self.session.scalar(
                select(TrainingSubmissionModel.submission_id).where(
                    TrainingSubmissionModel.task_id == task_id,
                    TrainingSubmissionModel.worker_id == worker_id,
                )
            )
        )

    def add_training_submission(self, submission: TrainingSubmissionModel) -> None:
        self.session.add(submission)

    def list_training_submissions(self, task_id: str) -> list[TrainingSubmissionModel]:
        return list(
            self.session.scalars(
                select(TrainingSubmissionModel)
                .where(TrainingSubmissionModel.task_id == task_id)
                .order_by(TrainingSubmissionModel.submitted_at_utc.desc())
            )
        )
