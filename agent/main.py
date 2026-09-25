from __future__ import annotations

from fastapi import FastAPI

from agent.api.chat import router as chat_router
from agent.api.camera_configs import router as camera_config_router
from agent.api.internal_perception import router as internal_router
from agent.api.public_safety import router as public_router
from agent.core.config import Settings
from agent.services.chat_service import ChatService
from agent.db.base import Database
from agent.llm.factory import create_chat_model
from agent.services.perception_service import PerceptionService


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()
    settings.validate_for_runtime()
    database = Database(settings.database_url)
    if settings.auto_create_schema:
        database.create_schema()

    app = FastAPI(title="Civil Engineering Safety Agent", version="0.1.0")
    app.state.settings = settings
    app.include_router(chat_router)
    app.state.perception_service = PerceptionService(database)
    app.include_router(internal_router)
    app.state.chat_service = ChatService(database, create_chat_model(settings), settings.tool_max_calls)
    app.include_router(camera_config_router)
    app.include_router(public_router)
    return app
