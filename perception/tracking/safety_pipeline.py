import time
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Iterable, List, Optional, Union
import numpy as np
from pydantic import BaseModel, Field

from perception.detectors.base import BaseDetector
from perception.geometry.topology import match_person_head_helmet
from perception.schemas.contract_v1 import (
    CameraRunConfigContractV1,
    TimeAnchor,
    to_event_contract_v1,
)
from perception.schemas.detection import (
    BoundingBox,
    DangerZone,
    TrackedPerson,
    ViolationEvent,
)
from perception.storage.event_store import EventStore
from perception.tracking.byte_tracker import BYTETracker
from perception.tracking.state_machine import WorkerSafetyMonitor

if TYPE_CHECKING:
    from perception.services.event_publisher import PerceptionEventPublisher


class PipelineFrameResult(BaseModel):
    """Encapsulates the end-to-end perception output for a single video frame."""
    frame_id: int = Field(..., description="Frame index")
    timestamp: float = Field(..., description="Timestamp in seconds")
    tracked_persons: List[TrackedPerson] = Field(default_factory=list, description="Currently tracked workers")
    new_violations: List[ViolationEvent] = Field(default_factory=list, description="Violations triggered in this frame")
    closed_violations: List[ViolationEvent] = Field(default_factory=list, description="Violations resolved in this frame")
    active_violations: List[ViolationEvent] = Field(default_factory=list, description="All currently active violations")
    raw_detections: List[BoundingBox] = Field(default_factory=list, description="Raw bounding boxes from detector")
    inference_time_ms: float = Field(0.0, description="Detection model execution time in ms")


class SafetyPerceptionPipeline:
    """
    Unified end-to-end perception and worker safety pipeline:
    Frame -> Detection -> Topology Matching -> Tracking -> State Machine -> Event Persistence & Contract Outbox.
    """

    def __init__(
        self,
        detector: BaseDetector,
        danger_zones: Optional[List[DangerZone]] = None,
        event_store: Optional[EventStore] = None,
        event_publisher: Optional["PerceptionEventPublisher"] = None,
        time_anchor: Optional[TimeAnchor] = None,
        monitor_session_id: str = "default_session",
        camera_id: str = "cam_01",
        enter_debounce_frames: int = 3,
        exit_debounce_frames: int = 5,
        helmet_debounce_frames: int = 5,
        track_thresh: float = 0.4,
        person_classes: Optional[Iterable[Union[str, int]]] = None,
        helmet_classes: Optional[Iterable[Union[str, int]]] = None,
        head_classes: Optional[Iterable[Union[str, int]]] = None,
        model_name: str = "helmet_head_person_m",
        model_version: str = "legacy-yolov5",
    ):
        self.detector = detector
        self.danger_zones = danger_zones or []
        self.event_store = event_store
        self.event_publisher = event_publisher
        self.time_anchor = time_anchor or TimeAnchor()
        self.monitor_session_id = monitor_session_id
        self.camera_id = camera_id

        self.person_classes = person_classes
        self.helmet_classes = helmet_classes
        self.head_classes = head_classes
        self.model_name = model_name
        self.model_version = model_version

        self.tracker = BYTETracker(track_thresh=track_thresh)
        self.safety_monitor = WorkerSafetyMonitor(
            camera_id=camera_id,
            enter_debounce_frames=enter_debounce_frames,
            exit_debounce_frames=exit_debounce_frames,
            helmet_debounce_frames=helmet_debounce_frames,
        )

        self.frame_counter: int = 0
        self.active_violations: List[ViolationEvent] = []

    def set_danger_zones(self, zones: List[DangerZone]):
        self.danger_zones = zones

    def set_time_anchor(self, time_anchor: TimeAnchor) -> None:
        self.time_anchor = time_anchor

    def update_config(
        self,
        enter_debounce_frames: Optional[int] = None,
        exit_debounce_frames: Optional[int] = None,
        helmet_debounce_frames: Optional[int] = None,
        danger_zones: Optional[List[DangerZone]] = None,
    ) -> None:
        """Dynamically updates debounce frames and danger zones at runtime."""
        self.safety_monitor.update_config(
            enter_debounce_frames=enter_debounce_frames,
            exit_debounce_frames=exit_debounce_frames,
            helmet_debounce_frames=helmet_debounce_frames,
        )
        if danger_zones is not None:
            self.danger_zones = danger_zones

    def reset(self):
        self.tracker.reset()
        self.safety_monitor = WorkerSafetyMonitor(
            camera_id=self.camera_id,
            enter_debounce_frames=self.safety_monitor.enter_debounce_frames,
            exit_debounce_frames=self.safety_monitor.exit_debounce_frames,
            helmet_debounce_frames=self.safety_monitor.helmet_debounce_frames,
        )
        self.frame_counter = 0
        self.active_violations.clear()

    def process_frame(
        self,
        frame: np.ndarray,
        timestamp: Optional[float] = None,
    ) -> PipelineFrameResult:
        """
        Executes full safety perception pipeline on a single image frame.
        :param frame: BGR uint8 numpy array
        :param timestamp: optional timestamp (monotonic or video time in seconds)
        :return: PipelineFrameResult with all tracked entities and safety events
        """
        self.frame_counter += 1
        now = time.monotonic() if timestamp is None else timestamp

        # 1. Run object detection
        det_result = self.detector.detect(frame)

        # 2. Perform person-head-helmet spatial topology matching
        topo_results = match_person_head_helmet(
            det_result.boxes,
            person_classes=self.person_classes,
            helmet_classes=self.helmet_classes,
            head_classes=self.head_classes,
        )

        # 3. Prepare person bounding boxes with attached helmet metadata for tracker
        person_boxes: List[BoundingBox] = []
        for res in topo_results:
            p_box = res.person_box.model_copy()
            p_box.has_helmet = res.has_helmet
            p_box.helmet_box = res.helmet_box
            p_box.head_box = res.head_box
            person_boxes.append(p_box)

        # 4. Multi-object tracking association
        tracked_persons = self.tracker.update(person_boxes)

        # 5. Safety state machine evaluation (debounce & dwell timing)
        new_events, closed_events = self.safety_monitor.process(
            tracked_persons=tracked_persons,
            danger_zones=self.danger_zones,
            current_time=now,
        )

        # 6. Update active violations list
        closed_uuids = {e.event_uuid for e in closed_events}
        self.active_violations = [v for v in self.active_violations if v.event_uuid not in closed_uuids]
        for e in new_events:
            # If escalating an existing event, update or replace
            existing_idx = next((i for i, v in enumerate(self.active_violations) if v.track_id == e.track_id and v.violation_type == e.violation_type), None)
            if existing_idx is not None:
                self.active_violations[existing_idx] = e
            else:
                self.active_violations.append(e)

        # 7. Persist events and snapshots if event_store is configured
        if self.event_store is not None:
            # Match person bbox and danger zone polygon for snapshot annotation
            track_box_map = {p.track_id: p.bbox for p in tracked_persons}
            zone_map = {z.name: z.polygon for z in self.danger_zones}

            for ev in new_events:
                p_box = track_box_map.get(ev.track_id)
                poly = zone_map.get(ev.zone_name) if ev.zone_name else None
                self.event_store.save_event(
                    event=ev,
                    frame=frame,
                    person_bbox=p_box,
                    zone_polygon=poly,
                )

            for ev in closed_events:
                self.event_store.close_event(
                    event_uuid=ev.event_uuid,
                    end_time=ev.end_time or now,
                    duration_seconds=ev.duration_seconds,
                )

        # 8. Dispatch events to Contract v1 Outbox / Publisher
        if self.event_publisher is not None:
            zone_id_map = {z.name: getattr(z, "zone_id", z.name) for z in self.danger_zones}

            for ev in new_events:
                contract_ev = to_event_contract_v1(
                    event=ev,
                    time_anchor=self.time_anchor,
                    monitor_session_id=self.monitor_session_id,
                    zone_id=zone_id_map.get(ev.zone_name) if ev.zone_name else None,
                    relative_snapshot_uri=ev.snapshot_path,
                    model_name=self.model_name,
                    model_version=self.model_version,
                )
                self.event_publisher.publish(contract_ev)

            for ev in closed_events:
                contract_ev = to_event_contract_v1(
                    event=ev,
                    time_anchor=self.time_anchor,
                    monitor_session_id=self.monitor_session_id,
                    zone_id=zone_id_map.get(ev.zone_name) if ev.zone_name else None,
                    relative_snapshot_uri=ev.snapshot_path,
                    model_name=self.model_name,
                    model_version=self.model_version,
                )
                self.event_publisher.publish(contract_ev)

        return PipelineFrameResult(
            frame_id=self.frame_counter,
            timestamp=now,
            tracked_persons=tracked_persons,
            new_violations=new_events,
            closed_violations=closed_events,
            active_violations=list(self.active_violations),
            raw_detections=det_result.boxes,
            inference_time_ms=det_result.inference_time_ms,
        )
