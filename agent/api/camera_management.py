from __future__ import annotations

from collections.abc import Iterator

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from fastapi.security import HTTPAuthorizationCredentials

from agent.api.dependencies import get_camera_management_service
from agent.contracts.camera_management import (
    CvNodeCreateRequest, CvNodeEnrollmentResponse, CvNodeHeartbeatRequest, CvNodeResponse,
    CvNodeMediaDirectoryResponse, ManagedCameraCreateRequest, ManagedCameraResponse,
    ManagedCameraSourceUpdate, MonitoringSessionResponse,
)
from agent.core.security import bearer_scheme, verify_admin_token
from agent.services.camera_management import CameraManagementError, CameraManagementService

router = APIRouter(prefix="/api/v1", tags=["camera-management"])
internal_router = APIRouter(prefix="/internal/v1/cv-nodes", tags=["internal-cv-nodes"])


def require_admin(request: Request, credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme)) -> None:
    verify_admin_token(credentials, request.app.state.settings)


def _http_error(exc: Exception) -> HTTPException:
    if isinstance(exc, KeyError):
        return HTTPException(status_code=404, detail="camera not found")
    if isinstance(exc, PermissionError):
        return HTTPException(status_code=403, detail=str(exc))
    return HTTPException(status_code=503, detail=str(exc))


@router.get("/cv-nodes", response_model=list[CvNodeResponse], dependencies=[Depends(require_admin)])
def list_cv_nodes(service: CameraManagementService = Depends(get_camera_management_service)) -> list[CvNodeResponse]:
    return service.list_nodes()


@router.post("/cv-nodes", response_model=CvNodeEnrollmentResponse, status_code=201, dependencies=[Depends(require_admin)])
def create_cv_node(request: CvNodeCreateRequest, service: CameraManagementService = Depends(get_camera_management_service)) -> CvNodeEnrollmentResponse:
    try:
        return service.create_node(request)
    except CameraManagementError as exc:
        raise HTTPException(status_code=409 if "already exists" in str(exc) else 503, detail=str(exc)) from exc


@router.get("/managed-cameras", response_model=list[ManagedCameraResponse], dependencies=[Depends(require_admin)])
def list_managed_cameras(service: CameraManagementService = Depends(get_camera_management_service)) -> list[ManagedCameraResponse]:
    return service.list_cameras()


@router.post("/managed-cameras", response_model=ManagedCameraResponse, status_code=201, dependencies=[Depends(require_admin)])
def create_managed_camera(request: ManagedCameraCreateRequest, service: CameraManagementService = Depends(get_camera_management_service)) -> ManagedCameraResponse:
    try:
        return service.create_camera(request)
    except CameraManagementError as exc:
        raise HTTPException(status_code=409 if "already exists" in str(exc) else 422, detail=str(exc)) from exc


@router.put("/managed-cameras/{camera_id}/source", response_model=ManagedCameraResponse, dependencies=[Depends(require_admin)])
def update_camera_source(camera_id: str, request: ManagedCameraSourceUpdate, service: CameraManagementService = Depends(get_camera_management_service)) -> ManagedCameraResponse:
    try:
        return service.update_source(camera_id, request)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/cv-nodes/{node_id}/media-files", response_model=CvNodeMediaDirectoryResponse, dependencies=[Depends(require_admin)])
def list_node_media_files(node_id: str, directory: str | None = None, service: CameraManagementService = Depends(get_camera_management_service)) -> CvNodeMediaDirectoryResponse:
    try:
        return service.list_node_media_files(node_id, directory)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/cameras/{camera_id}/monitoring:start", response_model=MonitoringSessionResponse, status_code=202, dependencies=[Depends(require_admin)])
def start_monitoring(camera_id: str, service: CameraManagementService = Depends(get_camera_management_service)) -> MonitoringSessionResponse:
    try:
        return service.start_camera(camera_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.post("/cameras/{camera_id}/monitoring:stop", response_model=MonitoringSessionResponse, dependencies=[Depends(require_admin)])
def stop_monitoring(camera_id: str, service: CameraManagementService = Depends(get_camera_management_service)) -> MonitoringSessionResponse:
    try:
        return service.stop_camera(camera_id)
    except Exception as exc:
        raise _http_error(exc) from exc


@router.get("/cameras/{camera_id}/preview")
def proxy_preview(camera_id: str, service: CameraManagementService = Depends(get_camera_management_service)) -> StreamingResponse:
    try:
        _, node = service.get_camera_and_node(camera_id)
        token = service._decrypt(node.control_token_encrypted)
    except Exception as exc:
        raise _http_error(exc) from exc

    def stream() -> Iterator[bytes]:
        try:
            with httpx.Client(trust_env=False, timeout=None) as client:
                with client.stream("GET", f"{node.control_url}/control/v1/sessions/{camera_id}/preview.mjpeg", headers={"Authorization": f"Bearer {token}"}) as response:
                    response.raise_for_status()
                    yield from response.iter_bytes()
        except httpx.HTTPError:
            return

    return StreamingResponse(stream(), media_type="multipart/x-mixed-replace; boundary=frame", headers={"Cache-Control": "no-store"})


@router.get("/cameras/{camera_id}/preview.jpg")
def proxy_preview_jpeg(camera_id: str, service: CameraManagementService = Depends(get_camera_management_service)) -> Response:
    """Proxy one newest CV frame; used by the zone editor's pause action."""
    try:
        _, node = service.get_camera_and_node(camera_id)
        token = service._decrypt(node.control_token_encrypted)
        with httpx.Client(trust_env=False, timeout=service.control_timeout_seconds) as client:
            upstream = client.get(
                f"{node.control_url}/control/v1/sessions/{camera_id}/preview.jpg",
                headers={"Authorization": f"Bearer {token}"},
            )
            upstream.raise_for_status()
    except Exception as exc:
        raise _http_error(exc) from exc
    return Response(content=upstream.content, media_type="image/jpeg", headers={"Cache-Control": "no-store"})


@internal_router.put("/{node_id}/heartbeat", response_model=CvNodeResponse)
def cv_node_heartbeat(node_id: str, request: CvNodeHeartbeatRequest, background_tasks: BackgroundTasks, credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme), service: CameraManagementService = Depends(get_camera_management_service)) -> CvNodeResponse:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="missing CV node bearer token")
    try:
        requires_recovery = service.node_requires_recovery(node_id)
        result = service.heartbeat_node(node_id, credentials.credentials, request)
        if requires_recovery:
            background_tasks.add_task(service.reconcile_node, node_id)
        return result
    except Exception as exc:
        raise _http_error(exc) from exc
