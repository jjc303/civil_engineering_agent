from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
import logging
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from agent.bootstrap import ROUTERS, build_service_container
from agent.core.config import Settings
from agent.db.base import Database

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
            if getattr(app.state, "notification_service", None) is not None:
                app.state.notification_service.shutdown(wait=False)

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

    container = build_service_container(settings, database)
    container.attach_to_app(app)

    for router in ROUTERS:
        app.include_router(router)

    return app
