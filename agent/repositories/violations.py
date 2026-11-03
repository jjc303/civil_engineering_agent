from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select, cast, Date, extract
from sqlalchemy.orm import Session

from agent.contracts.event_v1 import CameraStatusReportV1, SafetyViolationEventV1
from agent.contracts.query import CameraStatusResponse, RiskHeatmapResponse, ViolationQuery, ViolationRecord, ViolationStatisticsResponse
from agent.db.models import CameraConfigModel, CameraStatusModel, ManagedCameraModel, ViolationEventModel


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
        statement = self._event_statement(query)
        statement = statement.order_by(ViolationEventModel.occurred_at_utc.desc()).offset(query.offset).limit(query.limit)
        return [self._to_record(item) for item in self.session.scalars(statement)]

    def query_events_page(self, query: ViolationQuery) -> tuple[list[ViolationRecord], int]:
        statement = self._event_statement(query)
        total = self.session.scalar(select(func.count()).select_from(statement.subquery())) or 0
        statement = statement.order_by(ViolationEventModel.occurred_at_utc.desc()).offset(query.offset).limit(query.limit)
        return [self._to_record(item) for item in self.session.scalars(statement)], int(total)

    @staticmethod
    def _event_statement(query: ViolationQuery):
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
        return statement

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

    def get_risk_heatmap(self, lookback_days: int = 7, timezone_offset_hours: int = 8) -> RiskHeatmapResponse:
        """Aggregate violations into risk heatmap data for dashboard visualization."""
        now_utc = datetime.now(timezone.utc)
        cutoff_utc = now_utc - timedelta(days=lookback_days)

        # Base filter for time window
        base_filter = [ViolationEventModel.occurred_at_utc >= cutoff_utc]

        # Total count
        total = self.session.scalar(select(func.count()).select_from(ViolationEventModel).where(*base_filter)) or 0

        # Query time occurrences and severity, then project to local timezone
        tz_offset = timedelta(hours=timezone_offset_hours)
        now_local = (now_utc + tz_offset).date()

        time_rows = self.session.execute(
            select(ViolationEventModel.occurred_at_utc, ViolationEventModel.severity)
            .where(*base_filter)
        ).all()

        daily_map: dict[str, int] = {}
        hourly_agg: dict[int, dict[str, float]] = {h: {"count": 0, "weighted": 0.0} for h in range(24)}

        for dt_utc, severity in time_rows:
            if dt_utc is None:
                continue
            dt_local = dt_utc + tz_offset
            d_key = str(dt_local.date())
            daily_map[d_key] = daily_map.get(d_key, 0) + 1
            hour = dt_local.hour
            weight = {"CRITICAL": 3.0, "WARNING": 1.5, "INFO": 0.5}.get(severity, 1.0)
            hourly_agg[hour]["count"] += 1
            hourly_agg[hour]["weighted"] += weight

        daily_counts = [daily_map.get(str(now_local - timedelta(days=d)), 0) for d in range(lookback_days - 1, -1, -1)]

        max_weighted = max((d["weighted"] for d in hourly_agg.values()), default=1.0)
        hourly_risk = []
        for h in range(24):
            data = hourly_agg[h]
            risk_pct = data["weighted"] / max(max_weighted, 1.0) if max_weighted > 0 else 0.0
            risk_level = "CRITICAL" if risk_pct > 0.7 else "HIGH" if risk_pct > 0.4 else "MEDIUM" if risk_pct > 0.15 else "LOW"
            hourly_risk.append({"hour": h, "count": int(data["count"]), "risk_level": risk_level, "risk_pct": round(risk_pct, 3)})

        # Zone-level risks
        zone_rows = self.session.execute(
            select(
                ViolationEventModel.zone_name,
                ViolationEventModel.camera_id,
                ViolationEventModel.violation_type,
                ViolationEventModel.severity,
                func.count(),
            )
            .where(*base_filter, ViolationEventModel.zone_name.isnot(None))
            .group_by(ViolationEventModel.zone_name, ViolationEventModel.camera_id, ViolationEventModel.violation_type, ViolationEventModel.severity)
        ).all()

        zone_agg: dict[tuple[str, str], dict[str, Any]] = {}
        for zone_name, camera_id, vtype, severity, cnt in zone_rows:
            key = (str(zone_name), str(camera_id))
            if key not in zone_agg:
                zone_agg[key] = {"zone_name": str(zone_name), "camera_id": str(camera_id), "total": 0, "weighted": 0, "by_type": {}}
            w = {"CRITICAL": 3, "WARNING": 1.5, "INFO": 0.5}.get(severity, 1)
            zone_agg[key]["total"] += int(cnt)
            zone_agg[key]["weighted"] += int(cnt) * w
            zone_agg[key]["by_type"][str(vtype)] = zone_agg[key]["by_type"].get(str(vtype), 0) + int(cnt)

        max_zone_weighted = max((z["weighted"] for z in zone_agg.values()), default=1.0)
        zone_risks = []
        for key, z in sorted(zone_agg.items(), key=lambda item: -item[1]["weighted"]):
            z["risk_score"] = round(z["weighted"] / max(max_zone_weighted, 1.0), 3) if max_zone_weighted > 0 else 0.0
            z.pop("weighted")
            zone_risks.append(z)

        summary_lines = [f"近{lookback_days}天共{total}起违规"]
        high_hours = [r for r in hourly_risk if r["risk_level"] in ("HIGH", "CRITICAL")]
        if high_hours:
            top_hour = max(high_hours, key=lambda r: r["count"])
            summary_lines.append(f"高风险时段集中在{top_hour['hour']}:00前后")
        if zone_risks:
            summary_lines.append(f"最高风险区域：{zone_risks[0]['zone_name']}（{zone_risks[0]['total']}起）")
        summary = "；".join(summary_lines) + "。"

        return RiskHeatmapResponse(
            lookback_days=lookback_days,
            total_violations=int(total),
            daily_counts=daily_counts,
            hourly_risk=hourly_risk,
            zone_risks=zone_risks,
            summary=summary,
        )

    def get_camera_status(self, camera_id: str) -> CameraStatusResponse | None:
        model = self.session.get(CameraStatusModel, camera_id)
        managed = self.session.get(ManagedCameraModel, camera_id)
        if model:
            return self._effective_camera_status(model, managed, _utc_now())
        if managed:
            return self._unreported_camera_status(camera_id, managed.created_at_utc)
        return None

    def list_camera_statuses(self, now: datetime | None = None) -> list[CameraStatusResponse]:
        now = now or _utc_now()
        status_by_id = {model.camera_id: model for model in self.session.scalars(select(CameraStatusModel))}
        managed_by_id = {model.camera_id: model for model in self.session.scalars(select(ManagedCameraModel))}
        configured = {camera_id: updated_at for camera_id, updated_at in self.session.execute(select(CameraConfigModel.camera_id, CameraConfigModel.updated_at_utc))}
        results: list[CameraStatusResponse] = []

        for camera_id in sorted(set(status_by_id) | set(configured) | set(managed_by_id)):
            model = status_by_id.get(camera_id)
            if model is None:
                reported_at = configured.get(camera_id) or managed_by_id[camera_id].created_at_utc
                results.append(self._unreported_camera_status(camera_id, reported_at))
                continue

            results.append(self._effective_camera_status(model, managed_by_id.get(camera_id), now))

        return sorted(results, key=lambda item: (not item.is_online, item.camera_id))

    def list_managed_cameras(self) -> list[ManagedCameraModel]:
        return list(self.session.scalars(select(ManagedCameraModel).order_by(ManagedCameraModel.camera_id)))

    def get_workforce_summary(self) -> dict[str, object]:
        statuses = self.list_camera_statuses()
        online = [item for item in statuses if item.is_online]
        return {
            "active_workers_count": sum(item.active_workers_count for item in online),
            "online_camera_count": len(online),
            "camera_counts": [{"camera_id": item.camera_id, "active_workers_count": item.active_workers_count} for item in online],
        }

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

    @classmethod
    def _effective_camera_status(cls, model: CameraStatusModel, managed: ManagedCameraModel | None, now: datetime) -> CameraStatusResponse:
        item = cls._to_camera_status(model)
        reported_at = item.reported_at_utc
        if reported_at.tzinfo is None:
            reported_at = reported_at.replace(tzinfo=timezone.utc)
        fresh = (now - reported_at).total_seconds() <= 30
        session_active = managed is None or (managed.desired_state == "RUNNING" and managed.monitor_session_id == item.monitor_session_id)
        item.is_online = item.is_online and fresh and session_active
        if not item.is_online:
            item.fps = 0.0
            item.active_workers_count = 0
        return item

    @staticmethod
    def _unreported_camera_status(camera_id: str, reported_at: datetime) -> CameraStatusResponse:
        return CameraStatusResponse(
            camera_id=camera_id, monitor_session_id="unreported", is_online=False, fps=0.0,
            processed_frame_id=0, active_workers_count=0, model_name=None, model_version=None,
            reported_at_utc=reported_at, extra_details={},
        )
