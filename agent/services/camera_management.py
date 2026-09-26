from __future__ import annotations

import secrets
from datetime import datetime, timezone
from urllib.parse import urlsplit, urlunsplit

import httpx
from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select
from sqlalchemy.orm import Session

from agent.contracts.camera_management import (
    CvNodeCreateRequest, CvNodeEnrollmentResponse, CvNodeHeartbeatRequest, CvNodeResponse,
    CvNodeMediaDirectoryResponse, ManagedCameraCreateRequest, ManagedCameraResponse,
    ManagedCameraSourceUpdate, MonitoringSessionResponse,
)
from agent.db.base import Database
from agent.db.models import CvNodeModel, ManagedCameraModel


class CameraManagementError(RuntimeError):
    pass


class CameraManagementService:
    def __init__(self, database: Database, encryption_key: str, control_timeout_seconds: float = 10.0):
        self.database = database
        self.encryption_key = encryption_key
        self.control_timeout_seconds = control_timeout_seconds

    def _fernet(self) -> Fernet:
        if not self.encryption_key:
            raise CameraManagementError("AGENT_CREDENTIAL_ENCRYPTION_KEY must be configured for camera management")
        try:
            return Fernet(self.encryption_key.encode())
        except (ValueError, TypeError) as exc:
            raise CameraManagementError("AGENT_CREDENTIAL_ENCRYPTION_KEY must be a valid Fernet key") from exc

    def create_node(self, request: CvNodeCreateRequest) -> CvNodeEnrollmentResponse:
        token = request.control_token or secrets.token_urlsafe(32)
        with self.database.session() as session:
            if session.get(CvNodeModel, request.node_id):
                raise CameraManagementError("cv node already exists")
            model = CvNodeModel(
                node_id=request.node_id, display_name=request.display_name, control_url=str(request.control_url).rstrip("/"),
                control_token_encrypted=self._fernet().encrypt(token.encode()).decode(), capacity=request.capacity,
            )
            session.add(model)
            session.flush()
            return self._node_response(model, token)

    def list_nodes(self) -> list[CvNodeResponse]:
        with self.database.session() as session:
            return [self._node_response(item) for item in session.scalars(select(CvNodeModel).order_by(CvNodeModel.node_id)).all()]

    def heartbeat_node(self, node_id: str, token: str, request: CvNodeHeartbeatRequest) -> CvNodeResponse:
        with self.database.session() as session:
            node = session.get(CvNodeModel, node_id)
            if not node or not secrets.compare_digest(self._decrypt(node.control_token_encrypted), token):
                raise PermissionError("invalid CV node token")
            node.is_online = True
            node.active_sessions = request.active_sessions
            node.capacity = request.capacity
            node.last_heartbeat_at_utc = datetime.now(timezone.utc)
            return self._node_response(node)

    def node_requires_recovery(self, node_id: str) -> bool:
        """Return true only after a node has actually recovered/offlined."""
        with self.database.session() as session:
            node = session.get(CvNodeModel, node_id)
            if node is None or not node.is_online or node.last_heartbeat_at_utc is None:
                return True
            last = node.last_heartbeat_at_utc
            if last.tzinfo is None:
                last = last.replace(tzinfo=timezone.utc)
            return (datetime.now(timezone.utc) - last).total_seconds() > 30

    def create_camera(self, request: ManagedCameraCreateRequest) -> ManagedCameraResponse:
        with self.database.session() as session:
            if not session.get(CvNodeModel, request.node_id):
                raise CameraManagementError("selected CV node does not exist")
            if session.get(ManagedCameraModel, request.camera_id):
                raise CameraManagementError("camera already exists")
            model = ManagedCameraModel(
                camera_id=request.camera_id, display_name=request.display_name, node_id=request.node_id,
                source_type=request.source_type, source_uri_encrypted=self._fernet().encrypt(request.source_uri.encode()).decode(),
                source_uri_masked=self._mask(request.source_uri), desired_state="STOPPED",
            )
            session.add(model)
            session.flush()
            return self._camera_response(model)

    def list_cameras(self) -> list[ManagedCameraResponse]:
        with self.database.session() as session:
            return [self._camera_response(item) for item in session.scalars(select(ManagedCameraModel).order_by(ManagedCameraModel.camera_id)).all()]

    def update_source(self, camera_id: str, request: ManagedCameraSourceUpdate) -> ManagedCameraResponse:
        with self.database.session() as session:
            model = session.get(ManagedCameraModel, camera_id)
            if not model:
                raise KeyError(camera_id)
            if model.desired_state == "RUNNING":
                raise CameraManagementError("stop camera monitoring before editing its configuration")
            if not session.get(CvNodeModel, request.node_id):
                raise CameraManagementError("selected CV node does not exist")
            if request.display_name is not None:
                model.display_name = request.display_name
            source_changed = request.source_uri is not None
            target_changed = model.node_id != request.node_id or model.source_type != request.source_type
            if target_changed and not source_changed:
                raise CameraManagementError("provide a new video source when changing CV node or source type")
            if source_changed:
                model.node_id, model.source_type = request.node_id, request.source_type
                model.source_uri_encrypted = self._fernet().encrypt(request.source_uri.encode()).decode()
                model.source_uri_masked = self._mask(request.source_uri)
            return self._camera_response(model)

    def list_node_media_files(self, node_id: str, directory: str | None = None) -> CvNodeMediaDirectoryResponse:
        """Return files that the selected CV host explicitly permits browsing.

        The browser never talks to CV Control directly and cannot use a client
        machine file path as a node-local video source.
        """
        with self.database.session() as session:
            node = session.get(CvNodeModel, node_id)
            if not node:
                raise KeyError(node_id)
            if not node.is_online:
                raise CameraManagementError("selected CV node is offline")
            control_url = node.control_url
            token = self._decrypt(node.control_token_encrypted)
        try:
            with httpx.Client(timeout=self.control_timeout_seconds, trust_env=False) as client:
                response = client.get(
                    f"{control_url}/control/v1/media-files",
                    params={"directory": directory} if directory else None,
                    headers={"Authorization": f"Bearer {token}"},
                )
                response.raise_for_status()
                return CvNodeMediaDirectoryResponse.model_validate(response.json())
        except httpx.HTTPError as exc:
            raise CameraManagementError(f"CV media browser request failed: {exc}") from exc

    def start_camera(self, camera_id: str) -> MonitoringSessionResponse:
        return self._control(camera_id, "start")

    def stop_camera(self, camera_id: str) -> MonitoringSessionResponse:
        return self._control(camera_id, "stop")

    def get_camera_and_node(self, camera_id: str) -> tuple[ManagedCameraModel, CvNodeModel]:
        with self.database.session() as session:
            camera = session.get(ManagedCameraModel, camera_id)
            if not camera:
                raise KeyError(camera_id)
            node = session.get(CvNodeModel, camera.node_id)
            if not node:
                raise CameraManagementError("assigned CV node does not exist")
            session.expunge(camera); session.expunge(node)
            return camera, node

    def reconcile_node(self, node_id: str) -> None:
        """Best-effort recovery invoked after a CV node heartbeat.

        The desired state remains in Agent storage, so a restarted node gets its
        assigned RUNNING sessions back without exposing source credentials to Web.
        """
        with self.database.session() as session:
            camera_ids = list(session.scalars(
                select(ManagedCameraModel.camera_id).where(
                    ManagedCameraModel.node_id == node_id,
                    ManagedCameraModel.desired_state == "RUNNING",
                )
            ))
        for camera_id in camera_ids:
            try:
                self._control(camera_id, "start")
            except CameraManagementError:
                # A subsequent node heartbeat retries recovery; do not make
                # heartbeat delivery fail because a single stream is invalid.
                continue

    def _control(self, camera_id: str, action: str) -> MonitoringSessionResponse:
        with self.database.session() as session:
            camera = session.get(ManagedCameraModel, camera_id)
            if not camera:
                raise KeyError(camera_id)
            node = session.get(CvNodeModel, camera.node_id)
            if not node:
                raise CameraManagementError("assigned CV node does not exist")
            if not node.is_online:
                raise CameraManagementError("assigned CV node is offline")
            token = self._decrypt(node.control_token_encrypted)
            if action == "start":
                payload = {"camera_id": camera.camera_id, "source_type": camera.source_type, "source_uri": self._decrypt(camera.source_uri_encrypted)}
                method, url = httpx.post, f"{node.control_url}/control/v1/sessions"
            else:
                payload = None
                method, url = httpx.delete, f"{node.control_url}/control/v1/sessions/{camera.camera_id}"
        try:
            # CV Control is an internal/private endpoint.  Never inherit a
            # workstation HTTP proxy for loopback or site-network requests.
            with httpx.Client(timeout=self.control_timeout_seconds, trust_env=False) as client:
                response = client.request("POST" if action == "start" else "DELETE", url, json=payload, headers={"Authorization": f"Bearer {token}"})
                response.raise_for_status()
                body = response.json()
        except httpx.HTTPError as exc:
            raise CameraManagementError(f"CV control request failed: {exc}") from exc
        with self.database.session() as session:
            camera = session.get(ManagedCameraModel, camera_id)
            assert camera is not None
            camera.desired_state = "RUNNING" if action == "start" else "STOPPED"
            camera.monitor_session_id = body.get("monitor_session_id") if action == "start" else None
            return MonitoringSessionResponse(camera_id=camera_id, node_id=camera.node_id, monitor_session_id=camera.monitor_session_id, desired_state=camera.desired_state, accepted=True)

    def _decrypt(self, value: str) -> str:
        try:
            return self._fernet().decrypt(value.encode()).decode()
        except InvalidToken as exc:
            raise CameraManagementError("stored credential cannot be decrypted") from exc

    @staticmethod
    def _mask(source_uri: str) -> str:
        if source_uri.startswith(("rtsp://", "rtsps://")):
            parsed = urlsplit(source_uri)
            host = parsed.hostname or "hidden"
            port = f":{parsed.port}" if parsed.port else ""
            return urlunsplit((parsed.scheme, f"***:***@{host}{port}", parsed.path, "", ""))
        return f"file://…/{source_uri.rsplit('/', 1)[-1]}"

    @staticmethod
    def _node_response(model: CvNodeModel, token: str | None = None) -> CvNodeResponse:
        data = dict(node_id=model.node_id, display_name=model.display_name, control_url=model.control_url, is_online=model.is_online, active_sessions=model.active_sessions, capacity=model.capacity, last_heartbeat_at_utc=model.last_heartbeat_at_utc)
        return CvNodeEnrollmentResponse(**data, control_token=token) if token else CvNodeResponse(**data)

    @staticmethod
    def _camera_response(model: ManagedCameraModel) -> ManagedCameraResponse:
        return ManagedCameraResponse(camera_id=model.camera_id, display_name=model.display_name, node_id=model.node_id, source_type=model.source_type, source_uri_masked=model.source_uri_masked, desired_state=model.desired_state, monitor_session_id=model.monitor_session_id)
