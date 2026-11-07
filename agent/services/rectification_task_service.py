from __future__ import annotations

from agent.contracts.actions import PendingActionResponse
from agent.contracts.chat import ToolDecision
from agent.contracts.rectification import (
    RectificationTaskCreateRequest,
    RectificationTaskDetail,
    RectificationTaskPageResponse,
    RectificationTaskRecord,
    RectificationTaskUpdateRequest,
)
from agent.db.base import Database
from agent.repositories.rectification_tasks import RectificationTaskRepository
from agent.services.agent_write_actions import AgentWriteActionService


class RectificationTaskService:
    def __init__(self, database: Database, write_actions: AgentWriteActionService) -> None:
        self.database = database
        self.write_actions = write_actions

    def list_tasks(
        self,
        *,
        status: str | None,
        owner: str | None,
        overdue: bool | None,
        limit: int,
        offset: int,
    ) -> RectificationTaskPageResponse:
        with self.database.session() as session:
            items, total = RectificationTaskRepository(session).list_tasks(
                status=status, owner=owner, overdue=overdue, limit=limit, offset=offset
            )
            return RectificationTaskPageResponse(items=items, total=total, limit=limit, offset=offset)

    def get_task(self, task_id: str) -> RectificationTaskDetail:
        with self.database.session() as session:
            detail = RectificationTaskRepository(session).get_task_detail(task_id)
            if not detail:
                raise KeyError(task_id)
            return detail

    def propose_create(self, request: RectificationTaskCreateRequest) -> PendingActionResponse:
        return self.write_actions.propose(request.conversation_id, ToolDecision(
            tool_name="create_rectification_task", violation_event_uuid=request.event_uuid,
            task_title=request.title, task_description=request.description, task_owner=request.owner,
            task_due_at_utc=request.due_at_utc, purpose="页面人工创建关联违规的整改任务",
        ))

    def create_task(self, request: RectificationTaskCreateRequest) -> RectificationTaskRecord:
        """Directly create rectification task without pending confirmation delay (with audit)."""
        conv_id = request.conversation_id or "web-ui-direct"
        action_res = self.write_actions.execute_direct(
            conv_id,
            ToolDecision(
                tool_name="create_rectification_task",
                violation_event_uuid=request.event_uuid,
                task_title=request.title,
                task_description=request.description,
                task_owner=request.owner,
                task_due_at_utc=request.due_at_utc,
                purpose="页面人工创建关联违规的整改任务",
            ),
            actor="web-ui-direct",
        )
        task_id = action_res.result["task_id"]
        detail = self.get_task(task_id)
        return detail.task

    def propose_update(self, task_id: str, request: RectificationTaskUpdateRequest) -> PendingActionResponse:
        return self.write_actions.propose(request.conversation_id, ToolDecision(
            tool_name="update_rectification_task", task_id=task_id, task_owner=request.owner,
            task_due_at_utc=request.due_at_utc, task_status=request.status, task_note=request.note,
            purpose="页面更新整改任务",
        ))

    def update_task(self, task_id: str, request: RectificationTaskUpdateRequest) -> RectificationTaskRecord:
        """Directly update rectification task without pending confirmation delay (with audit)."""
        conv_id = request.conversation_id or "web-ui-direct"
        self.write_actions.execute_direct(
            conv_id,
            ToolDecision(
                tool_name="update_rectification_task",
                task_id=task_id,
                task_owner=request.owner,
                task_due_at_utc=request.due_at_utc,
                task_status=request.status,
                task_note=request.note,
                purpose="页面更新整改任务",
            ),
            actor="web-ui-direct",
        )
        detail = self.get_task(task_id)
        return detail.task

    # Compatibility alias
    _record = staticmethod(RectificationTaskRepository.to_record)
