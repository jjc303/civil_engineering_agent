from __future__ import annotations

from datetime import datetime, timezone

from agent.contracts.camera_config import CameraConfigUpdateRequest, CameraRunConfigV1
from agent.contracts.event_v1 import CameraStatusReportV1, EventUpsertResponse, SafetyViolationEventV1
from agent.contracts.query import CameraStatusResponse, SafetyQueryRequest, SafetyQueryResponse, ViolationQuery, ViolationRecord, ViolationStatisticsResponse
from agent.db.base import Database
from agent.repositories.camera_configs import CameraConfigRepository
from agent.repositories.violations import ViolationRepository


class PerceptionService:
    """Application service: transaction boundary for the Agent perception API."""

    def __init__(self, database: Database):
        self.database = database

    def upsert_event(self, event: SafetyViolationEventV1) -> EventUpsertResponse:
        with self.database.session() as session:
            record, operation = ViolationRepository(session).upsert_event(event)
            return EventUpsertResponse(
                event_uuid=record.event_uuid,
                operation=operation,
                status=record.status,
                server_received_at_utc=datetime.now(timezone.utc),
            )

    def upsert_camera_status(self, report: CameraStatusReportV1) -> CameraStatusResponse:
        with self.database.session() as session:
            return ViolationRepository(session).upsert_camera_status(report)

    def query_violations(self, query: ViolationQuery) -> list[ViolationRecord]:
        with self.database.session() as session:
            return ViolationRepository(session).query_events(query)


    def get_camera_config(self, camera_id: str) -> CameraRunConfigV1 | None:
        with self.database.session() as session:
            return CameraConfigRepository(session).get(camera_id)

    def update_camera_config(self, camera_id: str, request: CameraConfigUpdateRequest) -> CameraRunConfigV1:
        with self.database.session() as session:
            return CameraConfigRepository(session).upsert(camera_id, request)

    def get_statistics(self, query: ViolationQuery) -> ViolationStatisticsResponse:
        with self.database.session() as session:
            return ViolationRepository(session).get_statistics(query)

    def get_camera_status(self, camera_id: str) -> CameraStatusResponse | None:
        with self.database.session() as session:
            return ViolationRepository(session).get_camera_status(camera_id)

    def run_safety_query(self, request: SafetyQueryRequest) -> SafetyQueryResponse:
        from agent.graph.safety_graph import build_safety_graph

        with self.database.session() as session:
            graph = build_safety_graph(ViolationRepository(session))
            output = graph.invoke({"operation": request.operation, "query": request.query.model_dump(mode="json"), "camera_id": request.camera_id})
        return SafetyQueryResponse(operation=output["operation"], result=output["result"], summary=output["summary"])
