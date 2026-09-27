from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import select

from agent.contracts.actions import ActionExecutionResponse, PendingActionResponse
from agent.contracts.chat import ToolDecision
from agent.db.base import Database
from agent.db.models import (
    AgentPendingActionAuditModel,
    AgentPendingActionModel,
    RectificationTaskAuditModel,
    RectificationTaskModel,
    ViolationEventModel,
)
from agent.services.camera_management import CameraManagementService


class AgentWriteActionError(RuntimeError):
    """An expected, safe-to-display write-action rejection."""


_ACTOR = "agent-ui-confirmation"
_TTL = timedelta(minutes=15)


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


class AgentWriteActionService:
    """Stores proposed actions and executes them only after UI confirmation.

    The persisted payload is normalized server-side and deliberately contains
    no camera source URI, CV-node token, or other credential material.
    """

    def __init__(self, database: Database, camera_management: CameraManagementService | None) -> None:
        self.database = database
        self.camera_management = camera_management

    def propose(self, conversation_id: str | None, decision: ToolDecision) -> PendingActionResponse:
        if not conversation_id:
            raise AgentWriteActionError("执行写操作前需要有效的页面会话")
        if decision.tool_name == "create_rectification_task":
            return self._propose_task_create(conversation_id, decision)
        if decision.tool_name == "update_rectification_task":
            return self._propose_task_update(conversation_id, decision)
        if decision.tool_name in {"start_monitoring", "stop_monitoring"}:
            return self._propose_camera_control(conversation_id, decision)
        raise AgentWriteActionError("不支持的写操作")

    def _propose_task_create(self, conversation_id: str, decision: ToolDecision) -> PendingActionResponse:
        assert decision.violation_event_uuid and decision.task_title and decision.task_owner and decision.task_due_at_utc
        with self.database.session() as session:
            if not session.get(ViolationEventModel, decision.violation_event_uuid):
                raise AgentWriteActionError("关联的违规事件不存在，无法创建整改任务")
            payload = {
                "event_uuid": decision.violation_event_uuid,
                "title": decision.task_title.strip(),
                "description": (decision.task_description or "").strip(),
                "owner": decision.task_owner.strip(),
                "due_at_utc": _as_utc(decision.task_due_at_utc).isoformat(),
            }
            summary = f"创建整改任务：{payload['title']}；负责人：{payload['owner']}；截止：{_as_utc(decision.task_due_at_utc).strftime('%Y-%m-%d %H:%M UTC')}"
            return self._create_pending(session, conversation_id, decision.tool_name, summary, payload)

    def _propose_task_update(self, conversation_id: str, decision: ToolDecision) -> PendingActionResponse:
        assert decision.task_id
        with self.database.session() as session:
            task = session.get(RectificationTaskModel, decision.task_id)
            if not task:
                raise AgentWriteActionError("整改任务不存在")
            if task.status in {"COMPLETED", "CANCELLED"}:
                raise AgentWriteActionError("已完成或已取消的整改任务不可再编辑")
            payload: dict[str, Any] = {"task_id": decision.task_id}
            if decision.task_owner is not None:
                payload["owner"] = decision.task_owner.strip()
            if decision.task_due_at_utc is not None:
                payload["due_at_utc"] = _as_utc(decision.task_due_at_utc).isoformat()
            if decision.task_status is not None:
                payload["status"] = decision.task_status
            if decision.task_note is not None:
                payload["note"] = decision.task_note.strip()
            changes = []
            if "owner" in payload:
                changes.append(f"负责人改为 {payload['owner']}")
            if "due_at_utc" in payload:
                changes.append(f"截止时间改为 {_as_utc(decision.task_due_at_utc).strftime('%Y-%m-%d %H:%M UTC')}")
            if "status" in payload:
                changes.append(f"状态改为 {payload['status']}")
            if "note" in payload:
                changes.append("记录处理备注")
            return self._create_pending(session, conversation_id, decision.tool_name, f"更新整改任务 {decision.task_id[:8]}：{'；'.join(changes)}", payload)

    def _propose_camera_control(self, conversation_id: str, decision: ToolDecision) -> PendingActionResponse:
        assert decision.camera_id
        if not self.camera_management:
            raise AgentWriteActionError("摄像头管理服务未启用")
        try:
            camera, _ = self.camera_management.get_camera_and_node(decision.camera_id)
        except KeyError as exc:
            raise AgentWriteActionError("摄像头不存在") from exc
        action = "start" if decision.tool_name == "start_monitoring" else "stop"
        verb = "启动" if action == "start" else "停止"
        payload = {"camera_id": camera.camera_id, "action": action}
        with self.database.session() as session:
            return self._create_pending(session, conversation_id, decision.tool_name, f"{verb}监控：{camera.display_name}（{camera.camera_id}）", payload)

    def _create_pending(self, session: Any, conversation_id: str, action_type: str, summary: str, payload: dict[str, Any]) -> PendingActionResponse:
        now = _utc_now()
        model = AgentPendingActionModel(
            confirmation_id=str(uuid4()), conversation_id=conversation_id, action_type=action_type,
            summary=summary[:512], payload_safe_json=payload, status="PENDING",
            expires_at_utc=now + _TTL, result_safe_json={}, created_at_utc=now,
        )
        session.add(model)
        # SQLAlchemy has no ORM relationship between these two models. Flush
        # the parent before adding its FK-bound audit row (required by MySQL).
        session.flush()
        self._audit(session, model.confirmation_id, "PROPOSED", {"action_type": action_type})
        return PendingActionResponse(
            confirmation_id=model.confirmation_id, action_type=model.action_type, summary=model.summary,
            expires_at_utc=model.expires_at_utc, status="PENDING",
        )

    def confirm(self, confirmation_id: str, conversation_id: str) -> ActionExecutionResponse:
        # Camera controls must not keep a database transaction open during an
        # outbound CV request. Marking EXECUTING first also prevents duplicate
        # browser clicks from issuing a second control request.
        with self.database.session() as session:
            action = self._load_bound_action(session, confirmation_id, conversation_id)
            if action.status == "EXECUTED":
                return self._execution_response(action, idempotent=True)
            if action.status != "PENDING":
                raise AgentWriteActionError(f"该确认操作当前状态为 {action.status}，不能再次执行")
            if _as_utc(action.expires_at_utc) <= _utc_now():
                action.status = "EXPIRED"
                self._audit(session, action.confirmation_id, "EXPIRED", {})
                raise AgentWriteActionError("确认已过期，请重新发起操作")
            if action.action_type in {"start_monitoring", "stop_monitoring"}:
                action.status = "EXECUTING"
                self._audit(session, action.confirmation_id, "CONFIRMED", {})
                payload = dict(action.payload_safe_json or {})
            else:
                return self._execute_local(session, action)

        # The preceding transaction commits EXECUTING before crossing the
        # network boundary. No browser supplied camera credentials are used.
        assert self.camera_management is not None
        try:
            result = self.camera_management.start_camera(payload["camera_id"]) if payload["action"] == "start" else self.camera_management.stop_camera(payload["camera_id"])
            result_data = result.model_dump(mode="json")
        except Exception as exc:
            with self.database.session() as session:
                action = session.get(AgentPendingActionModel, confirmation_id)
                if action:
                    action.status = "FAILED"
                    action.failure_detail_safe = self._safe_error(exc)
                    self._audit(session, confirmation_id, "FAILED", {"reason": action.failure_detail_safe})
            raise AgentWriteActionError("摄像头控制未完成：" + self._safe_error(exc)) from exc
        with self.database.session() as session:
            action = session.get(AgentPendingActionModel, confirmation_id)
            if action is None:
                raise AgentWriteActionError("待确认操作不存在")
            action.status = "EXECUTED"
            action.executed_at_utc = _utc_now()
            action.result_safe_json = result_data
            self._audit(session, confirmation_id, "EXECUTED", result_data)
            return self._execution_response(action)

    def cancel(self, confirmation_id: str, conversation_id: str) -> ActionExecutionResponse:
        with self.database.session() as session:
            action = self._load_bound_action(session, confirmation_id, conversation_id)
            was_pending = action.status == "PENDING"
            if action.status == "PENDING":
                action.status = "CANCELLED"
                self._audit(session, confirmation_id, "CANCELLED", {})
            return self._execution_response(action, idempotent=not was_pending)

    def _execute_local(self, session: Any, action: AgentPendingActionModel) -> ActionExecutionResponse:
        payload = dict(action.payload_safe_json or {})
        if action.action_type == "create_rectification_task":
            now = _utc_now()
            task = RectificationTaskModel(
                task_id=str(uuid4()), event_uuid=payload["event_uuid"], title=payload["title"],
                description=payload.get("description") or None, owner=payload["owner"],
                due_at_utc=datetime.fromisoformat(payload["due_at_utc"]), status="PENDING",
                created_at_utc=now, updated_at_utc=now,
            )
            session.add(task)
            session.flush()
            self._task_audit(session, task.task_id, "CREATED", {"event_uuid": task.event_uuid, "owner": task.owner})
            result = {"task_id": task.task_id, "event_uuid": task.event_uuid, "status": task.status}
        elif action.action_type == "update_rectification_task":
            task = session.get(RectificationTaskModel, payload["task_id"])
            if not task:
                raise AgentWriteActionError("整改任务不存在")
            for field in ("owner", "status"):
                if field in payload:
                    setattr(task, field, payload[field])
            if "due_at_utc" in payload:
                task.due_at_utc = datetime.fromisoformat(payload["due_at_utc"])
            if payload.get("status") == "COMPLETED":
                task.completed_at_utc = _utc_now()
                violation = session.get(ViolationEventModel, task.event_uuid)
                if violation:
                    violation.status = "RESOLVED"
                    violation.resolved_at_utc = _utc_now()
            self._task_audit(session, task.task_id, "UPDATED", {key: value for key, value in payload.items() if key != "task_id"})
            result = {"task_id": task.task_id, "event_uuid": task.event_uuid, "status": task.status, "violation_resolved": payload.get("status") == "COMPLETED"}
        else:
            raise AgentWriteActionError("不支持的本地写操作")
        action.status = "EXECUTED"
        action.executed_at_utc = _utc_now()
        action.result_safe_json = result
        self._audit(session, action.confirmation_id, "EXECUTED", result)
        return self._execution_response(action)

    def _load_bound_action(self, session: Any, confirmation_id: str, conversation_id: str) -> AgentPendingActionModel:
        action = session.scalar(select(AgentPendingActionModel).where(AgentPendingActionModel.confirmation_id == confirmation_id).with_for_update())
        if not action:
            raise AgentWriteActionError("待确认操作不存在")
        if action.conversation_id != conversation_id:
            raise AgentWriteActionError("该确认操作不属于当前页面会话")
        return action

    @staticmethod
    def _execution_response(action: AgentPendingActionModel, idempotent: bool = False) -> ActionExecutionResponse:
        return ActionExecutionResponse(
            confirmation_id=action.confirmation_id, action_type=action.action_type, status=action.status,
            summary=action.summary, result=dict(action.result_safe_json or {}), idempotent=idempotent,
        )

    @staticmethod
    def _safe_error(exc: Exception) -> str:
        return str(exc).replace("\n", " ")[:400] or "未知错误"

    @staticmethod
    def _audit(session: Any, confirmation_id: str, action: str, detail: dict[str, Any]) -> None:
        session.add(AgentPendingActionAuditModel(
            audit_id=str(uuid4()), confirmation_id=confirmation_id, action=action, actor=_ACTOR,
            detail_safe_json=detail, created_at_utc=_utc_now(),
        ))

    @staticmethod
    def _task_audit(session: Any, task_id: str, action: str, detail: dict[str, Any]) -> None:
        session.add(RectificationTaskAuditModel(
            audit_id=str(uuid4()), task_id=task_id, action=action, actor=_ACTOR,
            detail_safe_json=detail, created_at_utc=_utc_now(),
        ))
