"""HTTP control plane for a single CV node.

The Agent is the only intended caller.  This service owns local file-path
interpretation, live runners and the MJPEG frame buffer; browsers never see a
source URI or contact this server directly.
"""
from __future__ import annotations

import os
import threading
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import requests
from fastapi import Depends, FastAPI, HTTPException, Response
from fastapi.responses import StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, Field, field_validator

from perception.services.event_publisher import OutboxStore, PerceptionEventPublisher
from perception.services.session_runner import CivilSafetyPerceptionService
from perception.storage.event_store import EventStore


@dataclass(frozen=True)
class CvControlSettings:
    node_id: str
    node_token: str
    agent_url: str
    internal_perception_token: str
    allowed_media_roots: tuple[Path, ...]
    capacity: int = 8
    heartbeat_interval_seconds: float = 5.0
    # This must be the same shared/mounted directory as
    # AGENT_MEDIA_ROOT/snapshots on the Agent host.
    snapshot_dir: Path | None = None

    @classmethod
    def from_env(cls) -> "CvControlSettings":
        roots = tuple(Path(item).resolve() for item in os.getenv("CV_ALLOWED_MEDIA_ROOTS", ".").split(os.pathsep) if item)
        return cls(
            node_id=os.getenv("CV_NODE_ID", ""), node_token=os.getenv("CV_NODE_TOKEN", ""),
            agent_url=os.getenv("AGENT_URL", "http://127.0.0.1:8000").rstrip("/"),
            internal_perception_token=os.getenv("INTERNAL_PERCEPTION_TOKEN", ""), allowed_media_roots=roots,
            capacity=int(os.getenv("CV_NODE_CAPACITY", "8")),
            heartbeat_interval_seconds=float(os.getenv("CV_NODE_HEARTBEAT_INTERVAL_SECONDS", "5")),
            snapshot_dir=Path(os.getenv("CV_SNAPSHOT_DIR", str(Path(os.getenv("AGENT_MEDIA_ROOT", "runs/media")) / "snapshots"))).resolve(),
        )


class StartSessionRequest(BaseModel):
    camera_id: str = Field(min_length=1, max_length=128)
    source_type: str
    source_uri: str = Field(min_length=1, max_length=1024)

    @field_validator("source_type")
    @classmethod
    def source_type_valid(cls, value: str) -> str:
        if value not in {"rtsp", "file"}:
            raise ValueError("source_type must be rtsp or file")
        return value


class MediaEntry(BaseModel):
    name: str
    path: str


class MediaDirectoryResponse(BaseModel):
    current_path: str
    parent_path: str | None = None
    directories: list[MediaEntry]
    files: list[MediaEntry]


def create_control_app(settings: CvControlSettings | None = None, service: CivilSafetyPerceptionService | None = None) -> FastAPI:
    settings = settings or CvControlSettings.from_env()
    if not settings.node_id or not settings.node_token:
        raise RuntimeError("CV_NODE_ID and CV_NODE_TOKEN must be configured")
    app = FastAPI(title="Civil Safety CV Control", version="1.0")
    app.state.settings = settings
    app.state.service = service or _build_service(settings)
    bearer = HTTPBearer(auto_error=False)

    def require_node_token(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> None:
        if credentials is None or credentials.scheme.lower() != "bearer" or credentials.credentials != settings.node_token:
            raise HTTPException(status_code=403, detail="invalid CV control token")

    @app.get("/control/v1/health", dependencies=[Depends(require_node_token)])
    def health() -> dict[str, object]:
        return {"node_id": settings.node_id, "active_sessions": len(app.state.service.runners)}

    @app.post("/control/v1/sessions", dependencies=[Depends(require_node_token)], status_code=202)
    def start_session(request: StartSessionRequest) -> dict[str, object]:
        source = _validate_source(request.source_type, request.source_uri, settings.allowed_media_roots)
        app.state.service.start_monitoring(request.camera_id, source, loop_video=request.source_type == "file", fps_throttle=request.source_type == "file")
        runner = app.state.service.runners[request.camera_id]
        return {"camera_id": request.camera_id, "monitor_session_id": runner.monitor_session_id, "accepted": True}

    @app.delete("/control/v1/sessions/{camera_id}", dependencies=[Depends(require_node_token)])
    def stop_session(camera_id: str) -> dict[str, object]:
        stopped = app.state.service.stop_monitoring(camera_id)
        if not stopped:
            raise HTTPException(status_code=404, detail="monitoring session not found")
        return {"camera_id": camera_id, "accepted": True}

    @app.get("/control/v1/sessions", dependencies=[Depends(require_node_token)])
    def list_sessions() -> list[dict[str, object]]:
        return [runner.get_status() for runner in app.state.service.runners.values()]

    @app.get("/control/v1/media-files", response_model=MediaDirectoryResponse, dependencies=[Depends(require_node_token)])
    def list_media_files(directory: str | None = None) -> MediaDirectoryResponse:
        return _list_media_files(directory, settings.allowed_media_roots)

    @app.get("/control/v1/sessions/{camera_id}/preview.mjpeg", dependencies=[Depends(require_node_token)])
    def preview(camera_id: str) -> StreamingResponse:
        runner = app.state.service.runners.get(camera_id)
        if runner is None:
            raise HTTPException(status_code=404, detail="monitoring session not found")

        def frames() -> Iterator[bytes]:
            while runner.is_running():
                frame = runner.latest_preview_jpeg()
                if frame:
                    yield b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: " + str(len(frame)).encode() + b"\r\n\r\n" + frame + b"\r\n"
                time.sleep(0.2)

        return StreamingResponse(frames(), media_type="multipart/x-mixed-replace; boundary=frame", headers={"Cache-Control": "no-store"})

    @app.get("/control/v1/sessions/{camera_id}/preview.jpg", dependencies=[Depends(require_node_token)])
    def preview_jpeg(camera_id: str) -> Response:
        """Return the latest decoded frame for a stable calibration background."""
        runner = app.state.service.runners.get(camera_id)
        if runner is None:
            raise HTTPException(status_code=404, detail="monitoring session not found")
        frame = runner.latest_preview_jpeg()
        if frame is None:
            raise HTTPException(status_code=503, detail="preview frame is not ready")
        return Response(content=frame, media_type="image/jpeg", headers={"Cache-Control": "no-store"})

    @app.on_event("startup")
    def start_heartbeat() -> None:
        thread = threading.Thread(target=_heartbeat_loop, args=(app,), daemon=True, name="cv-node-heartbeat")
        thread.start()

    return app


def _build_service(settings: CvControlSettings) -> CivilSafetyPerceptionService:
    publisher = PerceptionEventPublisher(
        outbox_store=OutboxStore(db_path=f"data/outbox-{settings.node_id}.db"), agent_base_url=settings.agent_url,
        bearer_token=settings.internal_perception_token,
    )
    snapshot_dir = settings.snapshot_dir or Path(os.getenv("CV_SNAPSHOT_DIR", str(Path(os.getenv("AGENT_MEDIA_ROOT", "runs/media")) / "snapshots"))).resolve()
    return CivilSafetyPerceptionService(
        event_publisher=publisher,
        event_store=EventStore(db_path=f"data/events-{settings.node_id}.db", snapshot_dir=snapshot_dir),
    )


def _validate_source(source_type: str, source_uri: str, roots: tuple[Path, ...]) -> str:
    if source_type == "rtsp":
        if not source_uri.startswith(("rtsp://", "rtsps://")):
            raise HTTPException(status_code=422, detail="RTSP source must use rtsp:// or rtsps://")
        return source_uri
    candidate = Path(source_uri).resolve()
    if not candidate.is_file() or not any(candidate.is_relative_to(root) for root in roots):
        raise HTTPException(status_code=422, detail="file source must exist under CV_ALLOWED_MEDIA_ROOTS")
    return str(candidate)


def _list_media_files(directory: str | None, roots: tuple[Path, ...]) -> MediaDirectoryResponse:
    if not roots:
        raise HTTPException(status_code=503, detail="CV_ALLOWED_MEDIA_ROOTS is empty")
    current = Path(directory).resolve() if directory else roots[0]
    if not current.is_dir() or not any(current.is_relative_to(root) for root in roots):
        raise HTTPException(status_code=422, detail="directory must exist under CV_ALLOWED_MEDIA_ROOTS")
    try:
        children = sorted(current.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower()))
    except OSError as exc:
        raise HTTPException(status_code=422, detail=f"cannot browse directory: {exc}") from exc
    allowed = [item.resolve() for item in children if any(item.resolve().is_relative_to(root) for root in roots)]
    directories = [MediaEntry(name=item.name, path=str(item)) for item in allowed if item.is_dir()]
    files = [MediaEntry(name=item.name, path=str(item)) for item in allowed if item.is_file() and item.suffix.lower() in {".mp4", ".avi", ".mov", ".mkv", ".webm", ".m4v"}]
    parent = current.parent if any(current != root for root in roots) and any(current.parent.is_relative_to(root) for root in roots) else None
    return MediaDirectoryResponse(current_path=str(current), parent_path=str(parent) if parent else None, directories=directories, files=files)


def _heartbeat_loop(app: FastAPI) -> None:
    settings: CvControlSettings = app.state.settings
    # Node-to-Agent traffic is internal.  Do not accidentally send loopback or
    # private-network heartbeats through a developer's HTTP proxy.
    with requests.Session() as session:
        session.trust_env = False
        while True:
            try:
                session.put(
                    f"{settings.agent_url}/internal/v1/cv-nodes/{settings.node_id}/heartbeat",
                    json={"active_sessions": len(app.state.service.runners), "capacity": settings.capacity},
                    headers={"Authorization": f"Bearer {settings.node_token}"}, timeout=3,
                )
            except requests.RequestException:
                pass
            time.sleep(settings.heartbeat_interval_seconds)


app = create_control_app
