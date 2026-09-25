import json
from pathlib import Path
import tempfile
import cv2
import pytest

from perception.detectors.base import BaseDetector
from perception.schemas.detection import BoundingBox, DangerZone, DetectionResult, ViolationSeverity, ViolationType
from perception.storage.event_store import EventStore
from perception.tracking.safety_pipeline import SafetyPerceptionPipeline

PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"


class ReplayDetector(BaseDetector):
    """Replays pre-annotated ground truth bounding boxes frame by frame."""

    def __init__(self, frame_annotations: list):
        super().__init__()
        self.frame_annotations = frame_annotations
        self.current_idx = 0

    def load_model(self, weights_path: Path) -> None:
        pass

    def detect(self, image) -> DetectionResult:

        if self.current_idx < len(self.frame_annotations):
            ann = self.frame_annotations[self.current_idx]
            self.current_idx += 1
            bx1, by1, bx2, by2 = ann["worker_bbox"]
            boxes = [
                BoundingBox(
                    x1=float(bx1),
                    y1=float(by1),
                    x2=float(bx2),
                    y2=float(by2),
                    conf=0.95,
                    class_id=0,
                    class_name="person",
                ),
                # Also supply a helmet on worker
                BoundingBox(
                    x1=float(bx1 + 10),
                    y1=float(by1 - 10),
                    x2=float(bx2 - 10),
                    y2=float(by1 + 25),
                    conf=0.92,
                    class_id=2,
                    class_name="helmet",
                ),
            ]
        else:
            boxes = []

        return DetectionResult(
            frame_id=self.current_idx,
            boxes=boxes,
            inference_time_ms=1.5,
        )


def test_safety_pipeline_end_to_end_on_sample_video():
    video_path = FIXTURES_DIR / "sample_walk.mp4"
    gt_path = FIXTURES_DIR / "ground_truth.json"

    with open(gt_path, "r", encoding="utf-8") as f:
        gt_data = json.load(f)

    danger_zone = DangerZone(
        name="Material_Zone_A",
        polygon=gt_data["danger_zones"][0]["polygon"],
        alarm_dwell_threshold_seconds=1.5,  # lower threshold to trigger in 5s clip
    )

    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "safety_events.db"
        snap_dir = Path(tmp_dir) / "snapshots"
        store = EventStore(db_path=db_path, snapshot_dir=snap_dir)

        detector = ReplayDetector(gt_data["frame_annotations"])
        pipeline = SafetyPerceptionPipeline(
            detector=detector,
            danger_zones=[danger_zone],
            event_store=store,
            camera_id="cam_site_01",
            enter_debounce_frames=3,
            exit_debounce_frames=3,
        )

        cap = cv2.VideoCapture(str(video_path))
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        frame_idx = 0

        intrusion_detected = False
        dwell_alarm_detected = False

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                break

            video_time = frame_idx / fps
            result = pipeline.process_frame(frame, timestamp=video_time)

            for ev in result.new_violations:
                if ev.violation_type == ViolationType.DANGER_ZONE_INTRUSION:
                    intrusion_detected = True
                    if ev.severity == ViolationSeverity.CRITICAL or ev.extra_details.get("escalation_reason") == "DWELL_TIMEOUT":
                        dwell_alarm_detected = True
                elif ev.violation_type == ViolationType.DWELL_TIMEOUT:
                    dwell_alarm_detected = True

            frame_idx += 1

        cap.release()

        # Check results
        assert intrusion_detected, "Danger zone intrusion was not detected by pipeline"
        assert dwell_alarm_detected, "Dwell timeout was not detected"

        # Check SQLite persistence
        persisted_events = store.query_events()
        assert len(persisted_events) >= 1

        # Check snapshot generation
        snapshots = list(snap_dir.glob("*/*.jpg"))
        assert len(snapshots) >= 1, "Snapshot image was not written to disk"


def test_safety_pipeline_with_event_publisher_outbox():
    """Verify that SafetyPerceptionPipeline publishes contract v1 events to the outbox."""
    from perception.services.event_publisher import OutboxStore, PerceptionEventPublisher
    from perception.schemas.contract_v1 import TimeAnchor

    video_path = FIXTURES_DIR / "sample_walk.mp4"
    ground_truth_path = FIXTURES_DIR / "ground_truth.json"

    with open(ground_truth_path, "r", encoding="utf-8") as f:
        gt_data = json.load(f)

    with tempfile.TemporaryDirectory() as tmp_dir:
        outbox_db = Path(tmp_dir) / "outbox.db"
        outbox_store = OutboxStore(db_path=outbox_db)
        publisher = PerceptionEventPublisher(
            outbox_store=outbox_store,
            agent_base_url="http://127.0.0.1:9999",
        )

        zone_data = gt_data["danger_zones"][0]
        danger_zone = DangerZone(
            name=zone_data["name"],
            polygon=zone_data["polygon"],
            alarm_dwell_threshold_seconds=1.0,
        )

        time_anchor = TimeAnchor(
            session_started_at_utc="2026-09-25T10:00:00Z",
            session_started_monotonic=0.0,
        )

        detector = ReplayDetector(gt_data["frame_annotations"])
        pipeline = SafetyPerceptionPipeline(
            detector=detector,
            danger_zones=[danger_zone],
            event_publisher=publisher,
            time_anchor=time_anchor,
            monitor_session_id="session_test_42",
            camera_id="cam_site_01",
            enter_debounce_frames=2,
            exit_debounce_frames=2,
        )

        cap = cv2.VideoCapture(str(video_path))
        fps = cap.get(cv2.CAP_PROP_FPS) or 25.0
        frame_idx = 0

        while cap.isOpened() and frame_idx < 95:
            ret, frame = cap.read()
            if not ret:
                break
            pipeline.process_frame(frame, timestamp=frame_idx / fps)
            frame_idx += 1

        cap.release()

        # Check outbox entries
        undelivered = outbox_store.get_all_events(delivered=False)
        assert len(undelivered) >= 1
        first = undelivered[0]
        payload = json.loads(first["payload_json"])
        assert payload["schema_version"] == "1.0"
        assert payload["camera_id"] == "cam_site_01"
        assert payload["monitor_session_id"] == "session_test_42"
        assert payload["event_uuid"] is not None

