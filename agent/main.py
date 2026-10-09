from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from agent.api.chat import router as chat_router
from agent.api.camera_configs import router as camera_config_router
from agent.api.internal_perception import router as internal_router
from agent.api.public_safety import router as public_router
from agent.core.config import Settings
from agent.services.chat_service import ChatService
from agent.db.base import Database
from agent.llm.factory import create_chat_model
from agent.services.perception_service import PerceptionService
from agent.services.camera_management import CameraManagementService
from agent.api.camera_management import router as camera_management_router, internal_router as cv_node_internal_router
from agent.api.knowledge import router as knowledge_router
from agent.api.ui_config import admin_router as ui_config_admin_router, public_router as ui_config_public_router
from agent.rag.chroma_adapter import ChromaKnowledgeRetriever
from agent.services.knowledge_service import KnowledgeService
from agent.services.agent_write_actions import AgentWriteActionService
from agent.services.rectification_task_service import RectificationTaskService
from agent.api.rectification_tasks import router as rectification_task_router
from agent.api.learning import router as learning_router, public_router as learning_public_router
from agent.services.learning_service import LearningService

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    settings.validate_for_runtime()
    database = Database(settings.database_url)
    if settings.auto_create_schema:
        database.create_schema()

    async def sync_knowledge_inbox_periodically(app: FastAPI) -> None:
        while True:
            try:
                await asyncio.to_thread(app.state.knowledge_service.sync_inbox)
            except Exception:
                logger.exception("Knowledge inbox synchronization failed")
            await asyncio.sleep(settings.rag_sync_interval_seconds)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        task: asyncio.Task[None] | None = None
        if app.state.knowledge_service.retriever is not None:
            # Indexing can take minutes for a large inbox or a remote embedding
            # provider. It must never hold up the HTTP readiness check.
            task = asyncio.create_task(sync_knowledge_inbox_periodically(app))
        try:
            yield
        finally:
            if task is not None:
                task.cancel()
                with suppress(asyncio.CancelledError):
                    await task

    app = FastAPI(title="Civil Engineering Safety Agent", version="0.1.0", lifespan=lifespan)
    media_root = Path(settings.media_root)
    media_root.mkdir(parents=True, exist_ok=True)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_origins),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.mount("/media", StaticFiles(directory=str(media_root)), name="media")
    app.state.settings = settings
    app.state.database = database
    app.include_router(chat_router)
    app.state.perception_service = PerceptionService(database)
    app.state.camera_management_service = CameraManagementService(database, settings.credential_encryption_key, settings.cv_control_timeout_seconds)
    app.include_router(internal_router)
    retriever = ChromaKnowledgeRetriever(
        settings.rag_persist_directory,
        settings.rag_embedding_provider,
        settings.rag_embedding_model,
        settings.rag_embedding_api_key,
        settings.rag_embedding_base_url,
        settings.rag_embedding_dimensions,
    ) if settings.rag_enabled else None
    app.state.knowledge_service = KnowledgeService(
        database, retriever, settings.rag_document_directory, settings.rag_inbox_directory,
        settings.rag_max_upload_bytes, settings.rag_allowed_extensions, settings.rag_chunk_size,
        settings.rag_chunk_overlap, settings.rag_top_k_max,
        standards_subdirectory=settings.rag_standards_subdirectory,
        accident_reports_subdirectory=settings.rag_accident_reports_subdirectory,
    )
    model = create_chat_model(settings)
    app.state.knowledge_service.set_summary_model(model)
    app.state.learning_service = LearningService(database, app.state.knowledge_service, model, settings.learning_report_directory, settings.learning_public_base_url, settings.learning_timezone, settings.learning_insights_ttl_seconds)
    app.state.agent_write_action_service = AgentWriteActionService(database, app.state.camera_management_service, app.state.learning_service)
    app.state.rectification_task_service = RectificationTaskService(database, app.state.agent_write_action_service)
    app.state.chat_service = ChatService(database, model, settings.tool_max_calls, settings.memory_enabled, settings.memory_ttl_hours, settings.memory_recent_turns, app.state.knowledge_service if retriever else None, app.state.agent_write_action_service, settings.rag_top_k, app.state.learning_service)
    app.include_router(camera_config_router)
    app.include_router(public_router)
    app.include_router(camera_management_router)
    app.include_router(cv_node_internal_router)
    app.include_router(knowledge_router)
    app.include_router(ui_config_public_router)
    app.include_router(ui_config_admin_router)
    app.include_router(rectification_task_router)
    app.include_router(learning_router)
    app.include_router(learning_public_router)

    return app
