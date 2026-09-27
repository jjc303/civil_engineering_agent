from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select

from agent.contracts.actions import PendingActionResponse
from agent.contracts.chat import ToolDecision
from agent.contracts.query import ViolationRecord
from agent.contracts.rectification import (
    RectificationTaskAudit,
    RectificationTaskCreateRequest,
    RectificationTaskDetail,
    RectificationTaskPageResponse,
    RectificationTaskRecord,
    RectificationTaskUpdateRequest,
)
from agent.db.base import Database
from agent.db.models import RectificationTaskAuditModel, RectificationTaskModel, ViolationEventModel
from agent.services.agent_write_actions import AgentWriteActionError, AgentWriteActionService


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class RectificationTaskService:
    def __init__(self, database: Database, write_actions: AgentWriteActionService) -> None:
        self.database = database
        self.write_actions = write_actions

    def list_tasks(self, *, status: str | None, owner: str | None, overdue: bool | None, limit: int, offset: int) -> RectificationTaskPageResponse:
        with self.database.session() as session:
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
            total = int(session.scalar(select(func.count()).select_from(statement.subquery())) or 0)
            rows = session.execute(
                statement.order_by(RectificationTaskModel.due_at_utc.asc(), RectificationTaskModel.created_at_utc.desc()).offset(offset).limit(limit)
            ).all()
            return RectificationTaskPageResponse(items=[self._record(task, event) for task, event in rows], total=total, limit=limit, offset=offset)

    def get_task(self, task_id: str) -> RectificationTaskDetail:
        with self.database.session() as session:
            row = session.execute(select(RectificationTaskModel, ViolationEventModel).join(
                ViolationEventModel, ViolationEventModel.event_uuid == RectificationTaskModel.event_uuid,
            ).where(RectificationTaskModel.task_id == task_id)).one_or_none()
            if not row:
                raise KeyError(task_id)
            task, event = row
            audits = list(session.scalars(select(RectificationTaskAuditModel).where(
                RectificationTaskAuditModel.task_id == task_id,
            ).order_by(RectificationTaskAuditModel.created_at_utc.desc())))
            return RectificationTaskDetail(
                task=self._record(task, event), violation=self._violation(event),
                audits=[RectificationTaskAudit(
                    audit_id=item.audit_id, task_id=item.task_id, action=item.action, actor=item.actor,
                    detail_safe_json=item.detail_safe_json or {}, created_at_utc=item.created_at_utc,
                ) for item in audits],
            )

    def propose_create(self, request: RectificationTaskCreateRequest) -> PendingActionResponse:
        return self.write_actions.propose(request.conversation_id, ToolDecision(
            tool_name="create_rectification_task", violation_event_uuid=request.event_uuid,
            task_title=request.title, task_description=request.description, task_owner=request.owner,
            task_due_at_utc=request.due_at_utc, purpose="页面人工创建关联违规的整改任务",
        ))

    def propose_update(self, task_id: str, request: RectificationTaskUpdateRequest) -> PendingActionResponse:
        return self.write_actions.propose(request.conversation_id, ToolDecision(
            tool_name="update_rectification_task", task_id=task_id, task_owner=request.owner,
            task_due_at_utc=request.due_at_utc, task_status=request.status, task_note=request.note,
            purpose="页面更新整改任务",
        ))

    @staticmethod
    def _record(task: RectificationTaskModel, event: ViolationEventModel) -> RectificationTaskRecord:
        return RectificationTaskRecord(
            task_id=task.task_id, event_uuid=task.event_uuid, title=task.title, description=task.description,
            owner=task.owner, due_at_utc=task.due_at_utc, status=task.status, completed_at_utc=task.completed_at_utc,
            created_at_utc=task.created_at_utc, updated_at_utc=task.updated_at_utc, camera_id=event.camera_id,
            violation_type=event.violation_type, severity=event.severity, violation_status=event.status,
            occurred_at_utc=event.occurred_at_utc, snapshot_uri=event.snapshot_uri,
        )

    @staticmethod
    def _violation(event: ViolationEventModel) -> ViolationRecord:
        return ViolationRecord(
            event_uuid=event.event_uuid, camera_id=event.camera_id, monitor_session_id=event.monitor_session_id,
            track_id=event.track_id, violation_type=event.violation_type, severity=event.severity, status=event.status,
            zone_id=event.zone_id, zone_name=event.zone_name, occurred_at_utc=event.occurred_at_utc,
            resolved_at_utc=event.resolved_at_utc, duration_seconds=event.duration_seconds, snapshot_uri=event.snapshot_uri,
            model_name=event.model_name, model_version=event.model_version, extra_details=event.extra_details or {},
        )
