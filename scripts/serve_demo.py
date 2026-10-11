"""Production Vue assets and the original FastAPI application on one port."""
from pathlib import Path
from starlette.exceptions import HTTPException
from fastapi.staticfiles import StaticFiles
from starlette.middleware.gzip import GZipMiddleware
from agent.main import create_app
from agent.core.deployment import DeploymentPathMiddleware

import os
ROOT = Path(__file__).resolve().parents[1]
# WEB_DIST_DIR 允许部署端改用其他目录名（云端托管可能剔除 dist 类构建产物目录）
DIST_DIR = Path(os.getenv("WEB_DIST_DIR", "web/dist"))
if not DIST_DIR.is_absolute():
    DIST_DIR = ROOT / DIST_DIR

class SpaFiles(StaticFiles):
    async def get_response(self, path, scope):
        path = path.replace('\\', '/')
        response = await self._get_spa_response(path, scope)
        if response.headers.get('content-type', '').startswith('text/html'):
            response.headers['cache-control'] = 'no-store'
        elif path.startswith('assets/'):
            response.headers['cache-control'] = 'public, max-age=31536000, immutable'
        return response

    async def _get_spa_response(self, path, scope):
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
    app.add_middleware(DeploymentPathMiddleware, prefix=app.state.settings.app_base_path)
    # Only static SPA assets: API/JPEG/MJPEG routes never enter this middleware.
    app.mount('/', GZipMiddleware(SpaFiles(directory=DIST_DIR, html=True), minimum_size=1024, compresslevel=6), name='console')
    return app
