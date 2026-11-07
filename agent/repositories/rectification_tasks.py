from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from agent.contracts.rectification import (
    RectificationTaskAudit,
    RectificationTaskDetail,
    RectificationTaskRecord,
)
from agent.db.models import (
    RectificationTaskAuditModel,
    RectificationTaskModel,
    ViolationEventModel,
)
from agent.repositories.violations import ViolationRepository


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RectificationTaskRepository:
    def __init__(self, session: Session) -> None:
        self.session = session

    def event_exists(self, event_uuid: str) -> bool:
        return self.session.get(ViolationEventModel, event_uuid) is not None

    def get_task_model(self, task_id: str) -> RectificationTaskModel | None:
        return self.session.get(RectificationTaskModel, task_id)

    def list_tasks(
        self,
        *,
        status: str | None = None,
        owner: str | None = None,
        overdue: bool | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> tuple[list[RectificationTaskRecord], int]:
        statement = select(RectificationTaskModel, ViolationEventModel).join(
            ViolationEventModel, ViolationEventModel.event_uuid == RectificationTaskModel.event_uuid,
        )
        if status:
            statement = statement.where(RectificationTaskModel.status == status)
        if owner:
            statement = statement.where(RectificationTaskModel.owner.like(f"%{owner.strip()}%"))
        if overdue is not None:
            active = RectificationTaskModel.status.in_(("PENDING", "IN_PROGRESS"))
            statement = statement.where(active, RectificationTaskModel.due_at_utc < _utc_now()) if overdue else statement.where(
                ~active | (RectificationTaskModel.due_at_utc >= _utc_now())
            )
        total = int(self.session.scalar(select(func.count()).select_from(statement.subquery())) or 0)
        rows = self.session.execute(
            statement.order_by(
                RectificationTaskModel.due_at_utc.asc(),
                RectificationTaskModel.created_at_utc.desc(),
            ).offset(offset).limit(limit)
        ).all()
        return [self.to_record(task, event) for task, event in rows], total

    def get_task_detail(self, task_id: str) -> RectificationTaskDetail | None:
        row = self.session.execute(
            select(RectificationTaskModel, ViolationEventModel).join(
                ViolationEventModel, ViolationEventModel.event_uuid == RectificationTaskModel.event_uuid,
            ).where(RectificationTaskModel.task_id == task_id)
        ).one_or_none()
        if not row:
            return None
        task, event = row
        audits = list(
            self.session.scalars(
                select(RectificationTaskAuditModel).where(
                    RectificationTaskAuditModel.task_id == task_id,
                ).order_by(RectificationTaskAuditModel.created_at_utc.desc())
            )
        )
        return RectificationTaskDetail(
            task=self.to_record(task, event),
            violation=ViolationRepository.to_record(event),
            audits=[
                RectificationTaskAudit(
                    audit_id=item.audit_id,
                    task_id=item.task_id,
                    action=item.action,
                    actor=item.actor,
                    detail_safe_json=item.detail_safe_json or {},
                    created_at_utc=item.created_at_utc,
                )
                for item in audits
            ],
        )

    def create_task(
        self,
        *,
        event_uuid: str,
        title: str,
        description: str | None,
        owner: str,
        due_at_utc: datetime,
        actor: str = "agent-ui-confirmation",
    ) -> RectificationTaskModel:
        now = _utc_now()
        task = RectificationTaskModel(
            task_id=str(uuid4()),
            event_uuid=event_uuid,
            title=title,
            description=description or None,
            owner=owner,
            due_at_utc=due_at_utc,
            status="PENDING",
            created_at_utc=now,
            updated_at_utc=now,
        )
        self.session.add(task)
        self.session.flush()
        self.record_audit(
            task_id=task.task_id,
            action="CREATED",
            actor=actor,
            detail={"event_uuid": task.event_uuid, "owner": task.owner},
        )
        return task

    def update_task(
        self,
        *,
        task_id: str,
        owner: str | None = None,
        due_at_utc: datetime | None = None,
        status: str | None = None,
        note: str | None = None,
        actor: str = "agent-ui-confirmation",
    ) -> tuple[RectificationTaskModel, bool]:
        task = self.session.get(RectificationTaskModel, task_id)
        if not task:
            raise KeyError(task_id)
        if owner is not None:
            task.owner = owner
        if status is not None:
            task.status = status
        if due_at_utc is not None:
            task.due_at_utc = due_at_utc
        violation_resolved = False
        if status == "COMPLETED":
            now = _utc_now()
            task.completed_at_utc = now
            violation = self.session.get(ViolationEventModel, task.event_uuid)
            if violation:
                violation.status = "RESOLVED"
                violation.resolved_at_utc = now
                violation_resolved = True
        audit_detail: dict[str, Any] = {}
        if owner is not None:
            audit_detail["owner"] = owner
        if due_at_utc is not None:
            audit_detail["due_at_utc"] = due_at_utc.isoformat()
        if status is not None:
            audit_detail["status"] = status
        if note is not None:
            audit_detail["note"] = note
        self.record_audit(
            task_id=task.task_id,
            action="UPDATED",
            actor=actor,
            detail=audit_detail,
        )
        return task, violation_resolved

    def record_audit(self, *, task_id: str, action: str, actor: str, detail: dict[str, Any]) -> None:
        self.session.add(
            RectificationTaskAuditModel(
                audit_id=str(uuid4()),
                task_id=task_id,
                action=action,
                actor=actor,
                detail_safe_json=detail,
                created_at_utc=_utc_now(),
            )
        )

    @staticmethod
    def to_record(task: RectificationTaskModel, event: ViolationEventModel) -> RectificationTaskRecord:
        return RectificationTaskRecord(
            task_id=task.task_id,
            event_uuid=task.event_uuid,
            title=task.title,
            description=task.description,
            owner=task.owner,
            due_at_utc=task.due_at_utc,
            status=task.status,
            completed_at_utc=task.completed_at_utc,
            created_at_utc=task.created_at_utc,
            updated_at_utc=task.updated_at_utc,
            camera_id=event.camera_id,
            violation_type=event.violation_type,
            severity=event.severity,
            violation_status=event.status,
            occurred_at_utc=event.occurred_at_utc,
            snapshot_uri=event.snapshot_uri,
        )
