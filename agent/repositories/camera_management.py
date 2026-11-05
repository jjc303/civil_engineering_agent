"""Repository encapsulating persistence operations for CV nodes and managed cameras."""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from agent.db.models import CameraStatusModel, CvNodeModel, ManagedCameraModel


class CameraManagementRepository:
    """Data access layer for CV control nodes and managed camera streams."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def get_node(self, node_id: str) -> CvNodeModel | None:
        return self.session.get(CvNodeModel, node_id)

    def add_node(self, node: CvNodeModel) -> CvNodeModel:
        self.session.add(node)
        self.session.flush()
        return node

    def list_nodes(self) -> list[CvNodeModel]:
        return list(
            self.session.scalars(
                select(CvNodeModel).order_by(CvNodeModel.node_id)
            ).all()
        )

    def get_camera(self, camera_id: str) -> ManagedCameraModel | None:
        return self.session.get(ManagedCameraModel, camera_id)

    def add_camera(self, camera: ManagedCameraModel) -> ManagedCameraModel:
        self.session.add(camera)
        self.session.flush()
        return camera

    def list_cameras(self) -> list[ManagedCameraModel]:
        return list(
            self.session.scalars(
                select(ManagedCameraModel).order_by(ManagedCameraModel.camera_id)
            ).all()
        )

    def list_running_camera_ids_for_node(self, node_id: str) -> list[str]:
        return list(
            self.session.scalars(
                select(ManagedCameraModel.camera_id).where(
                    ManagedCameraModel.node_id == node_id,
                    ManagedCameraModel.desired_state == "RUNNING",
                )
            )
        )

    def update_camera_session_state(
        self,
        camera_id: str,
        *,
        action: str,
        monitor_session_id: str | None,
    ) -> ManagedCameraModel:
        camera = self.session.get(ManagedCameraModel, camera_id)
        assert camera is not None
        camera.desired_state = "RUNNING" if action == "start" else "STOPPED"
        camera.monitor_session_id = monitor_session_id if action == "start" else None
        if action == "stop":
            status = self.session.get(CameraStatusModel, camera_id)
            if status is not None:
                status.is_online = False
                status.fps = 0.0
                status.active_workers_count = 0
                status.reported_at_utc = datetime.now(timezone.utc)
        self.session.flush()
        return camera
