from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from agent.contracts.event_v1 import CameraStatusReportV1, SafetyViolationEventV1
from agent.contracts.query import CameraStatusResponse, ViolationQuery, ViolationRecord, ViolationStatisticsResponse
from agent.db.models import CameraStatusModel, ViolationEventModel


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


class ViolationRepository:
    def __init__(self, session: Session):
        self.session = session

    def upsert_event(self, event: SafetyViolationEventV1) -> tuple[ViolationRecord, str]:
        key = str(event.event_uuid)
        model = self.session.get(ViolationEventModel, key)
        operation = "UPDATED" if model else "CREATED"
        if model is None:
            model = ViolationEventModel(event_uuid=key)
            self.session.add(model)

        for field, value in {
            "schema_version": event.schema_version,
            "camera_id": event.camera_id,
            "monitor_session_id": event.monitor_session_id,
            "track_id": event.track_id,
            "violation_type": event.violation_type.value,
            "severity": event.severity.value,
            "status": event.status.value,
            "zone_id": event.zone_id,
            "zone_name": event.zone_name,
            "occurred_at_utc": event.occurred_at_utc,
            "resolved_at_utc": event.resolved_at_utc,
            "duration_seconds": event.duration_seconds,
            "snapshot_uri": event.snapshot_uri,
            "model_name": event.model_name,
            "model_version": event.model_version,
            "extra_details": event.extra_details,
            "updated_at_utc": _utc_now(),
        }.items():
            setattr(model, field, value)
        self.session.flush()
        return self._to_record(model), operation

    def upsert_camera_status(self, report: CameraStatusReportV1) -> CameraStatusResponse:
        model = self.session.get(CameraStatusModel, report.camera_id)
        if model is None:
            model = CameraStatusModel(camera_id=report.camera_id)
            self.session.add(model)
        for field, value in report.model_dump().items():
            setattr(model, field, value)
        self.session.flush()
        return self._to_camera_status(model)

    def query_events(self, query: ViolationQuery) -> list[ViolationRecord]:
        statement = select(ViolationEventModel)
        if query.camera_id:
            statement = statement.where(ViolationEventModel.camera_id == query.camera_id)
        if query.violation_type:
            statement = statement.where(ViolationEventModel.violation_type == query.violation_type.value)
        if query.severity:
            statement = statement.where(ViolationEventModel.severity == query.severity.value)
        if query.status:
            statement = statement.where(ViolationEventModel.status == query.status.value)
        if query.start_time_utc:
            statement = statement.where(ViolationEventModel.occurred_at_utc >= query.start_time_utc)
        if query.end_time_utc:
            statement = statement.where(ViolationEventModel.occurred_at_utc <= query.end_time_utc)
        statement = statement.order_by(ViolationEventModel.occurred_at_utc.desc()).offset(query.offset).limit(query.limit)
        return [self._to_record(item) for item in self.session.scalars(statement)]

    def get_statistics(self, query: ViolationQuery) -> ViolationStatisticsResponse:
        filters = []
        if query.camera_id:
            filters.append(ViolationEventModel.camera_id == query.camera_id)
        if query.start_time_utc:
            filters.append(ViolationEventModel.occurred_at_utc >= query.start_time_utc)
        if query.end_time_utc:
            filters.append(ViolationEventModel.occurred_at_utc <= query.end_time_utc)
        total, average = self.session.execute(select(func.count(), func.avg(ViolationEventModel.duration_seconds)).where(*filters)).one()
        by_type = dict(self.session.execute(select(ViolationEventModel.violation_type, func.count()).where(*filters).group_by(ViolationEventModel.violation_type)).all())
        by_severity = dict(self.session.execute(select(ViolationEventModel.severity, func.count()).where(*filters).group_by(ViolationEventModel.severity)).all())
        return ViolationStatisticsResponse(total_violations=total or 0, average_duration_seconds=round(float(average or 0), 3), by_type=by_type, by_severity=by_severity)

    def get_camera_status(self, camera_id: str) -> CameraStatusResponse | None:
        model = self.session.get(CameraStatusModel, camera_id)
        return self._to_camera_status(model) if model else None

    @staticmethod
    def _to_record(model: ViolationEventModel) -> ViolationRecord:
        return ViolationRecord(
            event_uuid=model.event_uuid, camera_id=model.camera_id, monitor_session_id=model.monitor_session_id,
            track_id=model.track_id, violation_type=model.violation_type, severity=model.severity, status=model.status,
            zone_id=model.zone_id, zone_name=model.zone_name, occurred_at_utc=model.occurred_at_utc,
            resolved_at_utc=model.resolved_at_utc, duration_seconds=model.duration_seconds,
            snapshot_uri=model.snapshot_uri, model_name=model.model_name, model_version=model.model_version,
            extra_details=model.extra_details or {},
        )

    @staticmethod
    def _to_camera_status(model: CameraStatusModel) -> CameraStatusResponse:
        return CameraStatusResponse(**{field: getattr(model, field) for field in CameraStatusResponse.model_fields})
