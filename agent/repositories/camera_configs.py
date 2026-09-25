from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from agent.contracts.camera_config import CameraConfigUpdateRequest, CameraRunConfigV1, SourceResolution
from agent.db.models import CameraConfigModel


class ConfigVersionConflict(Exception):
    pass


class CameraConfigRepository:
    def __init__(self, session: Session):
        self.session = session

    def get(self, camera_id: str) -> CameraRunConfigV1 | None:
        model = self.session.get(CameraConfigModel, camera_id)
        return self._to_contract(model) if model else None

    def upsert(self, camera_id: str, request: CameraConfigUpdateRequest) -> CameraRunConfigV1:
        model = self.session.get(CameraConfigModel, camera_id)
        if model is None:
            if request.expected_version not in (None, 1):
                raise ConfigVersionConflict("camera configuration does not exist at the requested version")
            model = CameraConfigModel(camera_id=camera_id, config_version=1)
            self.session.add(model)
        else:
            if request.expected_version is not None and request.expected_version != model.config_version:
                raise ConfigVersionConflict("camera configuration version has changed")
            model.config_version += 1

        model.source_width = request.source_resolution.width
        model.source_height = request.source_resolution.height
        model.enter_debounce_frames = request.enter_debounce_frames
        model.exit_debounce_frames = request.exit_debounce_frames
        model.helmet_debounce_frames = request.helmet_debounce_frames
        model.alarm_dwell_threshold_seconds = request.alarm_dwell_threshold_seconds
        model.zones = [zone.model_dump(mode="json") for zone in request.zones]
        model.updated_at_utc = datetime.now(timezone.utc)
        self.session.flush()
        return self._to_contract(model)

    @staticmethod
    def _to_contract(model: CameraConfigModel) -> CameraRunConfigV1:
        return CameraRunConfigV1(
            camera_id=model.camera_id,
            config_version=model.config_version,
            source_resolution=SourceResolution(width=model.source_width, height=model.source_height),
            enter_debounce_frames=model.enter_debounce_frames,
            exit_debounce_frames=model.exit_debounce_frames,
            helmet_debounce_frames=model.helmet_debounce_frames,
            alarm_dwell_threshold_seconds=model.alarm_dwell_threshold_seconds,
            zones=model.zones or [],
        )
