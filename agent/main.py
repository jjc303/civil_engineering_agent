from __future__ import annotations

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


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    settings.validate_for_runtime()
    database = Database(settings.database_url)
    if settings.auto_create_schema:
        database.create_schema()

    app = FastAPI(title="Civil Engineering Safety Agent", version="0.1.0")
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
    retriever = ChromaKnowledgeRetriever(settings.rag_persist_directory, settings.rag_embedding_model) if settings.rag_enabled else None
    app.state.knowledge_service = KnowledgeService(database, retriever, settings.rag_document_directory, settings.rag_max_upload_bytes, settings.rag_allowed_extensions, settings.rag_chunk_size, settings.rag_chunk_overlap, settings.rag_top_k_max)
    app.state.chat_service = ChatService(database, create_chat_model(settings), settings.tool_max_calls, settings.memory_enabled, settings.memory_ttl_hours, settings.memory_recent_turns, app.state.knowledge_service if retriever else None)
    app.include_router(camera_config_router)
    app.include_router(public_router)
    app.include_router(camera_management_router)
    app.include_router(cv_node_internal_router)
    app.include_router(knowledge_router)
    app.include_router(ui_config_public_router)
    app.include_router(ui_config_admin_router)
    return app
