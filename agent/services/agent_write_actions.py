from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from uuid import uuid4

from sqlalchemy import select

from agent.contracts.actions import ActionExecutionResponse, PendingActionResponse
from agent.contracts.chat import ToolDecision
from agent.contracts.learning import ReportContent, ReportCreate, TrainingCreate, TrainingEdit
from agent.db.base import Database
from agent.db.models import AgentPendingActionAuditModel, AgentPendingActionModel
from agent.repositories.rectification_tasks import RectificationTaskRepository
from agent.services.camera_management import CameraManagementService
from agent.services.learning_service import LearningService


class AgentWriteActionError(RuntimeError):
    """An expected, safe-to-display write-action rejection."""


_ACTOR = "agent-ui-confirmation"
_TTL = timedelta(minutes=15)
_LEARNING_ACTIONS = {
    "create_safety_report", "update_safety_report", "confirm_safety_report", "delete_safety_report",
    "create_training_task", "update_training_task", "publish_training_task", "delete_training_task",
}


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _as_utc(value: datetime) -> datetime:
    return value.replace(tzinfo=timezone.utc) if value.tzinfo is None else value.astimezone(timezone.utc)


@dataclass(frozen=True)
class WriteActionHandlerSpec:
    action_type: str
    execution_mode: Literal["transactional", "external"]
    propose_fn: Callable[[AgentWriteActionService, str, ToolDecision], tuple[str, dict[str, Any]]]
    execute_fn: Callable[[AgentWriteActionService, Any, dict[str, Any]], tuple[dict[str, Any], tuple[str, dict[str, Any]] | None]]


class AgentWriteActionService:
    """Stores proposed actions and executes them only after UI confirmation.

    The persisted payload is normalized server-side and deliberately contains
    no camera source URI, CV-node token, or other credential material.
    """

    def __init__(
        self,
        database: Database,
        camera_management: CameraManagementService | None,
        learning_service: LearningService | None = None,
        notification_service: Any = None,
        pending_action_ttl_minutes: int = 15,
    ) -> None:
        self.database = database
        self.camera_management = camera_management
        self.learning_service = learning_service
        self.notification_service = notification_service
        self._ttl = timedelta(minutes=pending_action_ttl_minutes) if pending_action_ttl_minutes > 0 else _TTL
        self._handlers: dict[str, WriteActionHandlerSpec] = {}
        self._register_default_handlers()

    def register_action_handler(self, spec: WriteActionHandlerSpec) -> None:
        self._handlers[spec.action_type] = spec

    def _register_default_handlers(self) -> None:
        self.register_action_handler(WriteActionHandlerSpec(
            action_type="create_rectification_task",
            execution_mode="transactional",
            propose_fn=_propose_task_create,
            execute_fn=_exec_task_create,
        ))
        self.register_action_handler(WriteActionHandlerSpec(
            action_type="update_rectification_task",
            execution_mode="transactional",
            propose_fn=_propose_task_update,
            execute_fn=_exec_task_update,
        ))
        for action_type in ("start_monitoring", "stop_monitoring"):
            self.register_action_handler(WriteActionHandlerSpec(
                action_type=action_type,
                execution_mode="external",
                propose_fn=_propose_camera_control,
                execute_fn=_exec_camera_control,
            ))
        for action_type in _LEARNING_ACTIONS:
            def _make_learning_exec(act_type: str):
                return lambda s, _, p: (s._execute_learning(act_type, p), None)

            self.register_action_handler(WriteActionHandlerSpec(
                action_type=action_type,
                execution_mode="external",
                propose_fn=_propose_learning_action,
                execute_fn=_make_learning_exec(action_type),
            ))

    def propose(self, conversation_id: str | None, decision: ToolDecision) -> PendingActionResponse:
        if not conversation_id:
            raise AgentWriteActionError("执行写操作前需要有效的页面会话")
        handler = self._handlers.get(decision.tool_name)
        if not handler:
            raise AgentWriteActionError("不支持的写操作")
        summary, payload = handler.propose_fn(self, conversation_id, decision)
        with self.database.session() as session:
            return self._create_pending(session, conversation_id, decision.tool_name, summary, payload)

    def _create_pending(self, session: Any, conversation_id: str, action_type: str, summary: str, payload: dict[str, Any]) -> PendingActionResponse:
        now = _utc_now()
        model = AgentPendingActionModel(
            confirmation_id=str(uuid4()), conversation_id=conversation_id, action_type=action_type,
            summary=summary[:512], payload_safe_json=payload, status="PENDING",
            expires_at_utc=now + self._ttl, result_safe_json={}, created_at_utc=now,
        )
        session.add(model)
        session.flush()
        self._audit(session, model.confirmation_id, "PROPOSED", {"action_type": action_type})
        return PendingActionResponse(
            confirmation_id=model.confirmation_id, action_type=model.action_type, summary=model.summary,
            expires_at_utc=model.expires_at_utc, status="PENDING",
        )

    def confirm(self, confirmation_id: str, conversation_id: str) -> ActionExecutionResponse:
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

            handler = self._handlers.get(action.action_type)
            if not handler:
                raise AgentWriteActionError(f"不支持的写操作类型：{action.action_type}")

            if handler.execution_mode == "transactional":
                payload = dict(action.payload_safe_json or {})
                result_data, notify = handler.execute_fn(self, session, payload)
                action.status = "EXECUTED"
                action.executed_at_utc = _utc_now()
                action.result_safe_json = result_data
                self._audit(session, action.confirmation_id, "EXECUTED", result_data)
                if notify and self.notification_service is not None:
                    self._dispatch_notification(notify[0], notify[1])
                return self._execution_response(action)

            action.status = "EXECUTING"
            self._audit(session, action.confirmation_id, "CONFIRMED", {})
            payload = dict(action.payload_safe_json or {})
            action_type = action.action_type

        # Outside DB transaction
        try:
            result_data, notify = handler.execute_fn(self, None, payload)
        except Exception as exc:
            with self.database.session() as session:
                action = session.get(AgentPendingActionModel, confirmation_id)
                if action:
                    action.status = "FAILED"
                    action.failure_detail_safe = self._safe_error(exc)
                    self._audit(session, confirmation_id, "FAILED", {"reason": action.failure_detail_safe})
            prefix = "学习中心操作未完成：" if action_type in _LEARNING_ACTIONS else "摄像头控制未完成：" if action_type in {"start_monitoring", "stop_monitoring"} else "操作未完成："
            raise AgentWriteActionError(prefix + self._safe_error(exc)) from exc

        with self.database.session() as session:
            action = session.get(AgentPendingActionModel, confirmation_id)
            if action is None:
                raise AgentWriteActionError("待确认操作不存在")
            action.status = "EXECUTED"
            action.executed_at_utc = _utc_now()
            action.result_safe_json = result_data
            self._audit(session, confirmation_id, "EXECUTED", result_data)
            if notify and self.notification_service is not None:
                self._dispatch_notification(notify[0], notify[1])
            return self._execution_response(action)

    def cancel(self, confirmation_id: str, conversation_id: str) -> ActionExecutionResponse:
        with self.database.session() as session:
            action = self._load_bound_action(session, confirmation_id, conversation_id)
            was_pending = action.status == "PENDING"
            if action.status == "PENDING":
                action.status = "CANCELLED"
                self._audit(session, confirmation_id, "CANCELLED", {})
            return self._execution_response(action, idempotent=not was_pending)

    def _dispatch_notification(self, kind: str, payload: dict[str, Any]) -> None:
        if self.notification_service is None:
            return
        if kind == "created" and hasattr(self.notification_service, "notify_rectification_created"):
            self.notification_service.notify_rectification_created(payload)
        elif kind == "completed" and hasattr(self.notification_service, "notify_rectification_completed"):
            self.notification_service.notify_rectification_completed(payload)

    def _execute_learning(self, action_type: str, payload: dict[str, Any]) -> dict[str, Any]:
        learning = self.learning_service
        if learning is None:
            raise AgentWriteActionError("学习中心服务未启用")
        if action_type == "create_safety_report":
            report = learning.create_report(ReportCreate.model_validate(payload))
            return {"report_id": report.report_id, "status": report.status}
        if action_type == "update_safety_report":
            report = learning.edit_report(payload["report_id"], ReportContent.model_validate(payload["content"]))
            return {"report_id": report.report_id, "status": report.status}
        if action_type == "confirm_safety_report":
            report = learning.confirm_report(payload["report_id"])
            return {"report_id": report.report_id, "status": report.status, "pdf_url": report.pdf_url}
        if action_type == "delete_safety_report":
            learning.delete_report(payload["report_id"])
            return {"report_id": payload["report_id"], "status": "DELETED"}
        if action_type == "create_training_task":
            task = learning.create_training(TrainingCreate.model_validate(payload))
            return {"training_id": task.task_id, "status": task.status, "title": task.title}
        if action_type == "update_training_task":
            task = learning.edit_training(payload["training_id"], TrainingEdit.model_validate(payload["edit"]))
            return {"training_id": task.task_id, "status": task.status}
        if action_type == "publish_training_task":
            task = learning.publish_training(payload["training_id"])
            return {"training_id": task.task_id, "status": task.status, "public_url": task.public_url, "qr_url": task.qr_url}
        if action_type == "delete_training_task":
            learning.delete_training(payload["training_id"])
            return {"training_id": payload["training_id"], "status": "DELETED"}
        raise AgentWriteActionError("不支持的学习中心操作")

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


def _propose_task_create(service: AgentWriteActionService, conversation_id: str, decision: ToolDecision) -> tuple[str, dict[str, Any]]:
    assert decision.violation_event_uuid and decision.task_title and decision.task_owner and decision.task_due_at_utc
    with service.database.session() as session:
        repo = RectificationTaskRepository(session)
        if not repo.event_exists(decision.violation_event_uuid):
            raise AgentWriteActionError("关联的违规事件不存在，无法创建整改任务")
        payload = {
            "event_uuid": decision.violation_event_uuid,
            "title": decision.task_title.strip(),
            "description": (decision.task_description or "").strip(),
            "owner": decision.task_owner.strip(),
            "due_at_utc": _as_utc(decision.task_due_at_utc).isoformat(),
        }
        summary = f"创建整改任务：{payload['title']}；负责人：{payload['owner']}；截止：{_as_utc(decision.task_due_at_utc).strftime('%Y-%m-%d %H:%M UTC')}"
        return summary, payload


def _exec_task_create(service: AgentWriteActionService, session: Any, payload: dict[str, Any]) -> tuple[dict[str, Any], tuple[str, dict[str, Any]] | None]:
    repo = RectificationTaskRepository(session)
    task = repo.create_task(
        event_uuid=payload["event_uuid"],
        title=payload["title"],
        description=payload.get("description"),
        owner=payload["owner"],
        due_at_utc=datetime.fromisoformat(payload["due_at_utc"]),
    )
    result = {"task_id": task.task_id, "event_uuid": task.event_uuid, "status": task.status}
    notify = ("created", {
        "task_id": task.task_id,
        "event_uuid": task.event_uuid,
        "title": task.title,
        "description": task.description,
        "owner": task.owner,
        "due_at_utc": task.due_at_utc,
    })
    return result, notify


def _propose_task_update(service: AgentWriteActionService, conversation_id: str, decision: ToolDecision) -> tuple[str, dict[str, Any]]:
    assert decision.task_id
    with service.database.session() as session:
        repo = RectificationTaskRepository(session)
        task = repo.get_task_model(decision.task_id)
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
        return f"更新整改任务 {decision.task_id[:8]}：{'；'.join(changes)}", payload


def _exec_task_update(service: AgentWriteActionService, session: Any, payload: dict[str, Any]) -> tuple[dict[str, Any], tuple[str, dict[str, Any]] | None]:
    repo = RectificationTaskRepository(session)
    task_model = repo.get_task_model(payload["task_id"])
    if not task_model:
        raise AgentWriteActionError("整改任务不存在")
    due_at = datetime.fromisoformat(payload["due_at_utc"]) if "due_at_utc" in payload else None
    task, violation_resolved = repo.update_task(
        task_id=payload["task_id"],
        owner=payload.get("owner"),
        due_at_utc=due_at,
        status=payload.get("status"),
        note=payload.get("note"),
    )
    result = {
        "task_id": task.task_id,
        "event_uuid": task.event_uuid,
        "status": task.status,
        "violation_resolved": violation_resolved,
    }
    notify = None
    if payload.get("status") == "COMPLETED":
        notify = ("completed", {
            "task_id": task.task_id,
            "event_uuid": task.event_uuid,
            "title": task.title,
            "owner": task.owner,
            "note": payload.get("note"),
            "completed_at_utc": task.completed_at_utc,
        })
    return result, notify


def _propose_camera_control(service: AgentWriteActionService, conversation_id: str, decision: ToolDecision) -> tuple[str, dict[str, Any]]:
    assert decision.camera_id
    if not service.camera_management:
        raise AgentWriteActionError("摄像头管理服务未启用")
    try:
        camera, _ = service.camera_management.get_camera_and_node(decision.camera_id)
    except KeyError as exc:
        raise AgentWriteActionError("摄像头不存在") from exc
    action = "start" if decision.tool_name == "start_monitoring" else "stop"
    verb = "启动" if action == "start" else "停止"
    payload = {"camera_id": camera.camera_id, "action": action}
    return f"{verb}监控：{camera.display_name}（{camera.camera_id}）", payload


def _exec_camera_control(service: AgentWriteActionService, session: Any, payload: dict[str, Any]) -> tuple[dict[str, Any], tuple[str, dict[str, Any]] | None]:
    assert service.camera_management is not None
    result = (
        service.camera_management.start_camera(payload["camera_id"])
        if payload["action"] == "start"
        else service.camera_management.stop_camera(payload["camera_id"])
    )
    return result.model_dump(mode="json"), None


def _propose_learning_action(service: AgentWriteActionService, conversation_id: str, decision: ToolDecision) -> tuple[str, dict[str, Any]]:
    learning = service.learning_service
    if learning is None:
        raise AgentWriteActionError("学习中心服务未启用")
    name = decision.tool_name
    try:
        if name == "create_safety_report":
            request = learning.current_week_period() if decision.report_period == "THIS_WEEK" or not decision.report_period_start_utc else ReportCreate(
                period_start_utc=decision.report_period_start_utc, period_end_utc=decision.report_period_end_utc)
            payload = request.model_dump(mode="json")
            summary = f"生成安全报告草稿：{request.period_start_utc.isoformat()} 至 {request.period_end_utc.isoformat()}"
        elif name in {"update_safety_report", "confirm_safety_report", "delete_safety_report"}:
            assert decision.report_id
            report = learning.get_report(decision.report_id)
            if name in {"update_safety_report", "confirm_safety_report"} and report.status != "DRAFT":
                raise AgentWriteActionError("该报告已确认，不能再次修改或确认")
            payload = {"report_id": report.report_id}
            if name == "update_safety_report":
                content = report.content.model_dump()
                for field, value in (("summary", decision.report_summary), ("risk_analysis", decision.report_risk_analysis), ("remediation", decision.report_remediation)):
                    if value is not None:
                        content[field] = value.strip()
                payload["content"] = ReportContent.model_validate(content).model_dump()
            label = {"update_safety_report": "修改报告草稿", "confirm_safety_report": "确认报告并生成 PDF", "delete_safety_report": "删除报告及 PDF"}[name]
            summary = f"{label}：{report.report_id[:8]}（{report.period_start_utc.date()} 至 {report.period_end_utc.date()}）"
        elif name == "create_training_task":
            assert decision.report_id and decision.training_title and decision.training_target_count
            report = learning.get_report(decision.report_id)
            if report.status != "CONFIRMED":
                raise AgentWriteActionError("请先确认安全报告，再创建培训任务")
            request = TrainingCreate(report_id=report.report_id, title=decision.training_title.strip(),
                                     document_ids=decision.training_document_ids or [], target_count=decision.training_target_count,
                                     question_count=decision.training_question_count or 5,
                                     pass_score=80 if decision.training_pass_score is None else decision.training_pass_score)
            payload = request.model_dump(mode="json")
            summary = f"生成培训草稿：{request.title}；目标 {request.target_count} 人；{request.question_count} 道题"
        else:
            assert decision.training_id
            task = learning.get_training(decision.training_id)
            if name == "update_training_task" and task.status != "DRAFT":
                raise AgentWriteActionError("已发布的培训任务不可修改草稿")
            if name == "publish_training_task" and task.status != "DRAFT":
                raise AgentWriteActionError("培训任务已发布")
            payload = {"training_id": task.task_id}
            if name == "update_training_task":
                edit = TrainingEdit(
                    title=decision.training_title.strip() if decision.training_title else task.title,
                    target_count=decision.training_target_count or task.target_count,
                    pass_score=task.pass_score if decision.training_pass_score is None else decision.training_pass_score,
                    material=decision.training_material.strip() if decision.training_material else task.material,
                    questions=decision.training_questions if decision.training_questions is not None else task.questions,
                )
                payload["edit"] = edit.model_dump(mode="json")
            label = {"update_training_task": "修改培训草稿", "publish_training_task": "发布培训任务", "delete_training_task": "删除培训任务及答题成绩"}[name]
            summary = f"{label}：{task.title}（{task.task_id[:8]}）"
        return summary, payload
    except AgentWriteActionError:
        raise
    except KeyError as exc:
        raise AgentWriteActionError("指定的报告或培训任务不存在") from exc
    except ValueError as exc:
        raise AgentWriteActionError(f"学习中心参数无效：{exc}") from exc



