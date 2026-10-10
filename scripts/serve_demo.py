"""Production Vue assets and the original FastAPI application on one port."""
from pathlib import Path
from starlette.exceptions import HTTPException
from fastapi.staticfiles import StaticFiles
from agent.main import create_app

import os
ROOT = Path(__file__).resolve().parents[1]
# WEB_DIST_DIR 允许部署端改用其他目录名（云端托管可能剔除 dist 类构建产物目录）
DIST_DIR = Path(os.getenv("WEB_DIST_DIR", "web/dist"))
if not DIST_DIR.is_absolute():
    DIST_DIR = ROOT / DIST_DIR

class SpaFiles(StaticFiles):
    async def get_response(self, path, scope):
        if path.strip('/') == 'materials':
            return await super().get_response('index.html', scope)
        try:
            return await super().get_response(path, scope)
        except HTTPException as exc:
            if exc.status_code != 404 or path.startswith(('api/', 'internal/', 'media/', 'materials/', 'assets/')):
                raise
            return await super().get_response('index.html', scope)

def create_demo_app():
    app = create_app()
    app.mount('/', SpaFiles(directory=DIST_DIR, html=True), name='console')
    return app
