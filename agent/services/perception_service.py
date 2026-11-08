from __future__ import annotations

from datetime import datetime, timezone

from agent.contracts.camera_config import CameraConfigUpdateRequest, CameraRunConfigV1
from agent.contracts.event_v1 import CameraStatusReportV1, EventUpsertResponse, SafetyViolationEventV1
from agent.contracts.query import CameraStatusResponse, RiskHeatmapResponse, SafetyQueryRequest, SafetyQueryResponse, ViolationPageResponse, ViolationQuery, ViolationRecord, ViolationStatisticsResponse
from agent.db.base import Database
from agent.graph.safety_graph import COMPILED_SAFETY_GRAPH
from agent.notifications.protocol import NotificationPort
from agent.repositories.camera_configs import CameraConfigRepository
from agent.repositories.violations import ViolationRepository
from agent.tools.base import ToolContext


class PerceptionService:
    """Application service: transaction boundary for the Agent perception API."""

    def __init__(
        self,
        database: Database,
        notification_service: NotificationPort | None = None,
        cache: Any | None = None,
        event_stream: Any | None = None,
        broadcaster: Any | None = None,
        cache_camera_status_ttl_seconds: int = 30,
        cache_stats_ttl_seconds: int = 15,
    ):
        self.database = database
        self.notification_service = notification_service
        self.cache = cache
        self.event_stream = event_stream
        self.broadcaster = broadcaster
        self.cache_camera_status_ttl = cache_camera_status_ttl_seconds
        self.cache_stats_ttl = cache_stats_ttl_seconds
        self._safety_graph = COMPILED_SAFETY_GRAPH

    def upsert_event(self, event: SafetyViolationEventV1) -> EventUpsertResponse:
        with self.database.session() as session:
            record, operation = ViolationRepository(session).upsert_event(event)
            response = EventUpsertResponse(
                event_uuid=record.event_uuid,
                operation=operation,
                status=record.status,
                server_received_at_utc=datetime.now(timezone.utc),
            )
        if self.cache is not None:
            self.cache.invalidate_namespace("stats")

        if self.broadcaster is not None:
            try:
                self.broadcaster.publish("violation_event", {
                    "operation": operation,
                    "record": record.model_dump(mode="json"),
                })
            except Exception:
                pass

        if self.notification_service is not None and operation == "CREATED" and record.status == "ACTIVE":
            if self.event_stream is not None:
                self.event_stream.publish_event({
                    "event_type": "violation_event",
                    "record": record.model_dump(mode="json"),
                })
            else:
                self.notification_service.notify_violation_event(record)
        return response

    def upsert_camera_status(self, report: CameraStatusReportV1) -> CameraStatusResponse:
        with self.database.session() as session:
            repo = ViolationRepository(session)
            status_resp = repo.upsert_camera_status(report)
            effective_resp = repo.get_camera_status(report.camera_id) or status_resp
        if self.cache is not None:
            self.cache.set_json(
                "camera_status",
                report.camera_id,
                effective_resp.model_dump(mode="json"),
                ttl_seconds=self.cache_camera_status_ttl,
            )
        if self.broadcaster is not None:
            try:
                self.broadcaster.publish("camera_status", effective_resp.model_dump(mode="json"))
            except Exception:
                pass
        return status_resp

    def query_violations(self, query: ViolationQuery) -> list[ViolationRecord]:
        with self.database.session() as session:
            return ViolationRepository(session).query_events(query)

    def query_violations_page(self, query: ViolationQuery) -> ViolationPageResponse:
        with self.database.session() as session:
            items, total = ViolationRepository(session).query_events_page(query)
            return ViolationPageResponse(items=items, total=total, limit=query.limit, offset=query.offset)


    def get_camera_config(self, camera_id: str) -> CameraRunConfigV1 | None:
        with self.database.session() as session:
            return CameraConfigRepository(session).get(camera_id)

    def camera_exists(self, camera_id: str) -> bool:
        with self.database.session() as session:
            return ViolationRepository(session).camera_exists(camera_id)

    def update_camera_config(self, camera_id: str, request: CameraConfigUpdateRequest) -> CameraRunConfigV1:
        with self.database.session() as session:
            return CameraConfigRepository(session).upsert(camera_id, request)

    def get_statistics(self, query: ViolationQuery) -> ViolationStatisticsResponse:
        cache_key = None
        if self.cache is not None:
            cache_key = f"stats:{query.camera_id}:{query.start_time_utc}:{query.end_time_utc}"
            cached = self.cache.get_json("stats", cache_key)
            if cached is not None:
                return ViolationStatisticsResponse.model_validate(cached)

        with self.database.session() as session:
            stats = ViolationRepository(session).get_statistics(query)

        if self.cache is not None and cache_key is not None:
            self.cache.set_json("stats", cache_key, stats.model_dump(mode="json"), ttl_seconds=self.cache_stats_ttl)
        return stats

    def get_camera_status(self, camera_id: str) -> CameraStatusResponse | None:
        if self.cache is not None:
            cached = self.cache.get_json("camera_status", camera_id)
            if cached is not None:
                item = CameraStatusResponse.model_validate(cached)
                reported_at = item.reported_at_utc
                if reported_at.tzinfo is None:
                    reported_at = reported_at.replace(tzinfo=timezone.utc)
                if (datetime.now(timezone.utc) - reported_at).total_seconds() > 30:
                    item.is_online = False
                    item.fps = 0.0
                    item.active_workers_count = 0
                return item

        with self.database.session() as session:
            res = ViolationRepository(session).get_camera_status(camera_id)

        if res is not None and self.cache is not None:
            self.cache.set_json("camera_status", camera_id, res.model_dump(mode="json"), ttl_seconds=self.cache_camera_status_ttl)
        return res

    def list_camera_statuses(self) -> list[CameraStatusResponse]:
        with self.database.session() as session:
            return ViolationRepository(session).list_camera_statuses()

    def run_safety_query(self, request: SafetyQueryRequest) -> SafetyQueryResponse:
        with self.database.session() as session:
            ctx = ToolContext(repository=ViolationRepository(session))
            output = self._safety_graph.invoke(
                {"operation": request.operation, "query": request.query.model_dump(mode="json"), "camera_id": request.camera_id},
                config={"configurable": {"tool_context": ctx}},
            )
        return SafetyQueryResponse(operation=output["operation"], result=output["result"], summary=output["summary"])

    def get_risk_heatmap(self, lookback_days: int = 7, timezone_offset_hours: int = 8) -> RiskHeatmapResponse:
        cache_key = None
        if self.cache is not None:
            cache_key = f"heatmap:{lookback_days}:{timezone_offset_hours}"
            cached = self.cache.get_json("stats", cache_key)
            if cached is not None:
                return RiskHeatmapResponse.model_validate(cached)

        with self.database.session() as session:
            heatmap = ViolationRepository(session).get_risk_heatmap(lookback_days, timezone_offset_hours)

        if self.cache is not None and cache_key is not None:
            self.cache.set_json("stats", cache_key, heatmap.model_dump(mode="json"), ttl_seconds=self.cache_stats_ttl)
        return heatmap
