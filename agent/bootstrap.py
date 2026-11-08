"""Application bootstrap container and router registry for the Safety Agent."""
from __future__ import annotations

from dataclasses import dataclass
import logging
from typing import Any

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
from agent.contracts.query import ViolationRecord
from agent.core.config import Settings
from agent.db.base import Database
from agent.infra import InfraContainer, build_infra_container
from agent.llm.factory import create_chat_model
from agent.notifications import NotificationPort, create_notification_service
from agent.rag.chroma_adapter import ChromaKnowledgeRetriever
from agent.services.agent_write_actions import AgentWriteActionService
from agent.services.camera_management import CameraManagementService
from agent.services.chat_service import ChatService
from agent.services.knowledge_service import KnowledgeService
from agent.services.learning_service import LearningService
from agent.services.perception_service import PerceptionService
from agent.services.rectification_task_service import RectificationTaskService

logger = logging.getLogger(__name__)

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
    notification_service: NotificationPort
    perception_service: PerceptionService
    camera_management_service: CameraManagementService
    knowledge_service: KnowledgeService
    learning_service: LearningService
    agent_write_action_service: AgentWriteActionService
    rectification_task_service: RectificationTaskService
    chat_service: ChatService
    infra: InfraContainer | None = None

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
        if self.infra is not None:
            app.state.infra = self.infra
            app.state.cache = self.infra.cache
            app.state.lock_service = self.infra.lock_service
            app.state.broadcaster = self.infra.broadcaster


def build_service_container(settings: Settings, database: Database, infra: InfraContainer | None = None) -> ServiceContainer:
    infra = infra or build_infra_container(settings)
    notification_service = create_notification_service(settings, throttle=infra.throttle)
    perception_service = PerceptionService(
        database,
        notification_service=notification_service,
        cache=infra.cache,
        event_stream=infra.event_stream if settings.stream_async_enabled else None,
        broadcaster=infra.broadcaster,
        cache_camera_status_ttl_seconds=settings.cache_camera_status_ttl_seconds,
        cache_stats_ttl_seconds=settings.cache_stats_ttl_seconds,
    )
    camera_management_service = CameraManagementService(
        database,
        settings.credential_encryption_key,
        settings.cv_control_timeout_seconds,
        settings.cv_node_offline_threshold_seconds,
        lock_service=infra.lock_service,
        lock_ttl_seconds=settings.lock_default_ttl_seconds,
        cache=infra.cache,
        broadcaster=infra.broadcaster,
    )
    retriever = (
        ChromaKnowledgeRetriever(
            settings.rag_persist_directory,
            settings.rag_embedding_provider,
            settings.rag_embedding_model,
            settings.rag_embedding_api_key,
            settings.rag_embedding_base_url,
            settings.rag_embedding_dimensions,
            collection_name=settings.rag_collection_name,
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
        cache=infra.cache,
    )
    agent_write_action_service = AgentWriteActionService(
        database,
        camera_management_service,
        learning_service,
        notification_service=notification_service,
        pending_action_ttl_minutes=settings.pending_action_ttl_minutes,
        lock_service=infra.lock_service,
        lock_ttl_seconds=settings.lock_action_confirm_ttl_seconds,
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
        standards_on_demand=settings.rag_standards_on_demand,
    )

    if settings.stream_async_enabled and notification_service is not None:
        def _handle_stream_event(payload: dict[str, Any]) -> None:
            if payload.get("event_type") == "violation_event":
                record_data = payload.get("record")
                if record_data:
                    try:
                        record = ViolationRecord.model_validate(record_data)
                        notification_service.notify_violation_event(record)
                    except Exception as err:
                        logger.warning("Stream consumer notification failed: %s", err)

        infra.event_stream.start_consumer(_handle_stream_event)

    return ServiceContainer(
        notification_service=notification_service,
        perception_service=perception_service,
        camera_management_service=camera_management_service,
        knowledge_service=knowledge_service,
        learning_service=learning_service,
        agent_write_action_service=agent_write_action_service,
        rectification_task_service=rectification_task_service,
        chat_service=chat_service,
        infra=infra,
    )
