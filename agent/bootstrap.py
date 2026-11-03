"""Application bootstrap container and router registry for the Safety Agent."""
from __future__ import annotations

from dataclasses import dataclass

from fastapi import APIRouter, FastAPI

from agent.api.camera_configs import router as camera_config_router
from agent.api.camera_management import internal_router as cv_node_internal_router, router as camera_management_router
from agent.api.chat import router as chat_router
from agent.api.internal_perception import router as internal_router
from agent.api.knowledge import router as knowledge_router
from agent.api.learning import public_router as learning_public_router, router as learning_router
from agent.api.meta import router as meta_router
from agent.api.public_safety import router as public_router
from agent.api.rectification_tasks import router as rectification_task_router
from agent.api.ui_config import admin_router as ui_config_admin_router, public_router as ui_config_public_router
from agent.core.config import Settings
from agent.db.base import Database
from agent.llm.factory import create_chat_model
from agent.notifications import FeishuNotificationService
from agent.rag.chroma_adapter import ChromaKnowledgeRetriever
from agent.services.agent_write_actions import AgentWriteActionService
from agent.services.camera_management import CameraManagementService
from agent.services.chat_service import ChatService
from agent.services.knowledge_service import KnowledgeService
from agent.services.learning_service import LearningService
from agent.services.perception_service import PerceptionService
from agent.services.rectification_task_service import RectificationTaskService

ROUTERS: tuple[APIRouter, ...] = (
    chat_router,
    internal_router,
    camera_config_router,
    public_router,
    camera_management_router,
    cv_node_internal_router,
    knowledge_router,
    ui_config_public_router,
    ui_config_admin_router,
    rectification_task_router,
    learning_router,
    learning_public_router,
    meta_router,
)


@dataclass
class ServiceContainer:
    notification_service: FeishuNotificationService
    perception_service: PerceptionService
    camera_management_service: CameraManagementService
    knowledge_service: KnowledgeService
    learning_service: LearningService
    agent_write_action_service: AgentWriteActionService
    rectification_task_service: RectificationTaskService
    chat_service: ChatService

    def attach_to_app(self, app: FastAPI) -> None:
        app.state.services = self
        app.state.notification_service = self.notification_service
        app.state.perception_service = self.perception_service
        app.state.camera_management_service = self.camera_management_service
        app.state.knowledge_service = self.knowledge_service
        app.state.learning_service = self.learning_service
        app.state.agent_write_action_service = self.agent_write_action_service
        app.state.rectification_task_service = self.rectification_task_service
        app.state.chat_service = self.chat_service


def build_service_container(settings: Settings, database: Database) -> ServiceContainer:
    notification_service = FeishuNotificationService(
        settings.feishu_webhook_url,
        webhook_secret=settings.feishu_webhook_secret,
        enabled=settings.feishu_notify_enabled,
        web_base_url=settings.feishu_web_base_url or settings.learning_public_base_url or "http://127.0.0.1:5173",
        timezone_name=settings.learning_timezone,
        cooldown_seconds=settings.feishu_alert_cooldown_seconds,
        min_severity=settings.feishu_alert_min_severity,
        timeout_seconds=settings.feishu_timeout_seconds,
    )
    perception_service = PerceptionService(database, notification_service=notification_service)
    camera_management_service = CameraManagementService(
        database, settings.credential_encryption_key, settings.cv_control_timeout_seconds
    )
    retriever = (
        ChromaKnowledgeRetriever(
            settings.rag_persist_directory,
            settings.rag_embedding_provider,
            settings.rag_embedding_model,
            settings.rag_embedding_api_key,
            settings.rag_embedding_base_url,
            settings.rag_embedding_dimensions,
        )
        if settings.rag_enabled
        else None
    )
    knowledge_service = KnowledgeService(
        database,
        retriever,
        settings.rag_document_directory,
        settings.rag_inbox_directory,
        settings.rag_max_upload_bytes,
        settings.rag_allowed_extensions,
        settings.rag_chunk_size,
        settings.rag_chunk_overlap,
        settings.rag_top_k_max,
        standards_subdirectory=settings.rag_standards_subdirectory,
        accident_reports_subdirectory=settings.rag_accident_reports_subdirectory,
    )
    model = create_chat_model(settings)
    knowledge_service.set_summary_model(model)
    learning_service = LearningService(
        database,
        knowledge_service,
        model,
        settings.learning_report_directory,
        settings.learning_public_base_url,
        settings.learning_timezone,
        settings.learning_insights_ttl_seconds,
        app_base_path=settings.app_base_path,
        notification_service=notification_service,
        report_source_label=settings.report_source_label,
    )
    agent_write_action_service = AgentWriteActionService(
        database,
        camera_management_service,
        learning_service,
        notification_service=notification_service,
        pending_action_ttl_minutes=settings.pending_action_ttl_minutes,
    )
    rectification_task_service = RectificationTaskService(database, agent_write_action_service)
    chat_service = ChatService(
        database,
        model,
        settings.tool_max_calls,
        settings.memory_enabled,
        settings.memory_ttl_hours,
        settings.memory_recent_turns,
        knowledge_service if retriever else None,
        agent_write_action_service,
        settings.rag_top_k,
        learning_service,
        notification_service=notification_service,
    )
    return ServiceContainer(
        notification_service=notification_service,
        perception_service=perception_service,
        camera_management_service=camera_management_service,
        knowledge_service=knowledge_service,
        learning_service=learning_service,
        agent_write_action_service=agent_write_action_service,
        rectification_task_service=rectification_task_service,
        chat_service=chat_service,
    )
