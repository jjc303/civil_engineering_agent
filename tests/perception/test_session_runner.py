"""
Tests for CameraSessionRunner, CivilSafetyPerceptionService, and Periodic Heartbeat / Config Polling.
"""

import time
import json
import tempfile
from pathlib import Path
from typing import Optional, List, Dict, Any
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import numpy as np
import cv2

from perception.services.session_runner import CameraSessionRunner, CivilSafetyPerceptionService
from perception.services.event_publisher import OutboxStore, PerceptionEventPublisher
from perception.storage.event_store import EventStore
from perception.schemas.contract_v1 import (
    CameraStatusContractV1,
    CameraRunConfigContractV1,
    CameraZoneConfig,
    TimeAnchor,
)
from perception.schemas.detection import (
    BoundingBox,
    DetectionResult,
    ViolationEvent,
    ViolationType,
    ViolationSeverity,
)
from perception.detectors.base import BaseDetector
from perception.geometry.danger_zone import DangerZone

FIXTURES_DIR = Path(__file__).resolve().parent.parent / "fixtures"


class MockReplayDetector(BaseDetector):
    """Mock detector returning predetermined detections for tests."""
    def __init__(self, boxes: Optional[list] = None):
        self.boxes = boxes or [
            BoundingBox(x1=100, y1=100, x2=200, y2=300, conf=0.9, class_id=0, class_name="person"),
            BoundingBox(x1=110, y1=100, x2=190, y2=150, conf=0.85, class_id=2, class_name="helmet"),
        ]

    def load_model(self, weights_path: str, device: str = "cpu") -> None:
        pass

    def detect(self, image: np.ndarray, conf_threshold: float = 0.4, iou_threshold: float = 0.5) -> DetectionResult:
        return DetectionResult(
            frame_id=1,
            timestamp=time.time(),
            boxes=self.boxes,
            inference_time_ms=5.0,
        )


def test_file_source_uses_monotonic_timestamps_for_time_anchor():
    """File playback must not pass frame-relative seconds into TimeAnchor."""
    video_path = FIXTURES_DIR / "sample_walk.mp4"
    received_timestamps: list[float] = []

    class CapturingPipeline:
        def __init__(self, **_kwargs):
            self.frame_counter = 0
            self.active_violations = []

        def process_frame(self, _frame, timestamp):
            self.frame_counter += 1
            received_timestamps.append(timestamp)
            return SimpleNamespace(tracked_persons=[])

    runner = CameraSessionRunner(
        camera_id="cam_file_clock_01",
        source=str(video_path),
        detector=MockReplayDetector(),
        heartbeat_interval=0.05,
    )

    with patch("perception.services.session_runner.SafetyPerceptionPipeline", CapturingPipeline):
        runner.start()
        time.sleep(0.1)
        runner.stop(timeout=2.0)

    assert received_timestamps
    assert runner.time_anchor is not None
    # Video time starts close to zero; monotonic time shares the anchor's epoch.
    assert min(received_timestamps) >= runner.time_anchor.session_started_monotonic


def test_session_runner_lifecycle_and_heartbeat():
    """Verify start/stop lifecycle and initial/final heartbeats."""
    video_path = FIXTURES_DIR / "sample_walk.mp4"

    with tempfile.TemporaryDirectory() as tmp_dir:
        outbox_db = Path(tmp_dir) / "outbox.db"
        outbox_store = OutboxStore(db_path=outbox_db)

        # Mock publisher
        mock_publisher = MagicMock(spec=PerceptionEventPublisher)
        mock_publisher.fetch_camera_config.return_value = None  # Fallback to local
        mock_publisher.report_camera_status.return_value = True

        detector = MockReplayDetector()
        danger_zone = DangerZone(
            name="TestZone",
            polygon=[(0, 0), (500, 0), (500, 500), (0, 500)],
        )

        runner = CameraSessionRunner(
            camera_id="cam_test_01",
            source=str(video_path),
            detector=detector,
            publisher=mock_publisher,
            danger_zones=[danger_zone],
            heartbeat_interval=0.1,  # fast heartbeat for test
        )

        session_id = runner.start()
        assert session_id.startswith("session_cam_test_01")
        assert runner.is_running()

        # Allow runner to process a few frames and trigger heartbeat
        time.sleep(0.4)

        status = runner.get_status()
        assert status["camera_id"] == "cam_test_01"
        assert status["is_online"] is True
        assert status["processed_frame_id"] > 0

        # Stop runner
        runner.stop(timeout=2.0)
        assert not runner.is_running()

        # Verify heartbeats were reported
        assert mock_publisher.report_camera_status.call_count >= 2
        # Check that the last call reported is_online=False
        last_reported_status: CameraStatusContractV1 = mock_publisher.report_camera_status.call_args[0][0]
        assert last_reported_status.is_online is False
        assert last_reported_status.camera_id == "cam_test_01"


def test_session_runner_graceful_config_fallback():
    """Verify that when Agent config endpoint returns None (404), runner falls back to default danger zones."""
    video_path = FIXTURES_DIR / "sample_walk.mp4"

    mock_publisher = MagicMock(spec=PerceptionEventPublisher)
    mock_publisher.fetch_camera_config.return_value = None  # Agent has no config

    detector = MockReplayDetector()
    runner = CameraSessionRunner(
        camera_id="cam_fallback_01",
        source=str(video_path),
        detector=detector,
        publisher=mock_publisher,
        # No initial_danger_zones provided -> must fallback to default_danger_zones.json
    )

    zones = runner._fetch_or_fallback_zones()
    assert len(zones) >= 1
    assert any("Excavator" in z.name or "Hazard" in z.name or "Zone" in z.name for z in zones)


def test_session_runner_dynamic_config_hot_reload():
    """Verify dynamic config polling hot-reloads zones when config_version increments."""
    video_path = FIXTURES_DIR / "sample_walk.mp4"

    mock_publisher = MagicMock(spec=PerceptionEventPublisher)
    # Initial config v1
    v1_config = CameraRunConfigContractV1(
        camera_id="cam_reload_01",
        config_version=1,
        enter_debounce_frames=3,
        zones=[
            CameraZoneConfig(
                zone_id="zone_01",
                zone_name="Initial_Zone",
                polygon=[[0.0, 0.0], [100.0, 0.0], [100.0, 100.0], [0.0, 100.0]],
            )
        ],
    )
    mock_publisher.fetch_camera_config.return_value = v1_config

    detector = MockReplayDetector()
    runner = CameraSessionRunner(
        camera_id="cam_reload_01",
        source=str(video_path),
        detector=detector,
        publisher=mock_publisher,
        config_poll_interval=0.1,
    )

    runner.start()
    time.sleep(0.2)

    assert runner.pipeline is not None
    assert len(runner.pipeline.danger_zones) == 1
    assert runner.pipeline.danger_zones[0].name == "Initial_Zone"

    # Now simulate Agent publishing new config v2 with an extra zone
    v2_config = CameraRunConfigContractV1(
        camera_id="cam_reload_01",
        config_version=2,
        enter_debounce_frames=1,
        zones=[
            CameraZoneConfig(
                zone_id="zone_01",
                zone_name="Initial_Zone",
                polygon=[[0.0, 0.0], [100.0, 0.0], [100.0, 100.0], [0.0, 100.0]],
            ),
            CameraZoneConfig(
                zone_id="zone_02",
                zone_name="Updated_Crane_Zone",
                polygon=[[200.0, 200.0], [400.0, 200.0], [400.0, 400.0], [200.0, 400.0]],
            ),
        ],
    )
    mock_publisher.fetch_camera_config.return_value = v2_config

    # Wait for dynamic config poll
    time.sleep(0.3)
    runner.stop(timeout=2.0)

    # Verify pipeline was hot-reloaded with new zones
    assert len(runner.pipeline.danger_zones) == 2
    assert runner.pipeline.danger_zones[1].name == "Updated_Crane_Zone"
    assert runner.pipeline.safety_monitor.enter_debounce_frames == 1


def test_civil_safety_perception_service():
    """Verify CivilSafetyPerceptionService multi-camera control, status query, and daily report generation."""
    video_path = FIXTURES_DIR / "sample_walk.mp4"

    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "events.db"
        event_store = EventStore(db_path=db_path, snapshot_dir=Path(tmp_dir) / "snapshots")

        # Insert some synthetic events for daily report
        today_iso = "2026-09-25T10:00:00Z"
        ev1 = ViolationEvent(
            event_uuid="ev-daily-01",
            track_id=1,
            camera_id="cam_crane_01",
            violation_type=ViolationType.DANGER_ZONE_INTRUSION,
            severity=ViolationSeverity.WARNING,
            zone_name="Crane_Zone",
            start_time=10.0,
            duration_seconds=5.0,
            created_at=today_iso,
        )
        ev2 = ViolationEvent(
            event_uuid="ev-daily-02",
            track_id=2,
            camera_id="cam_crane_01",
            violation_type=ViolationType.NO_HELMET,
            severity=ViolationSeverity.CRITICAL,
            start_time=20.0,
            end_time=30.0,
            duration_seconds=10.0,
            created_at=today_iso,
        )
        event_store.save_event(ev1)
        event_store.save_event(ev2)

        detector = MockReplayDetector()
        service = CivilSafetyPerceptionService(
            detector=detector,
            event_store=event_store,
        )

        # Start monitoring
        started = service.start_monitoring(
            camera_id="cam_crane_01",
            stream_url=str(video_path),
            zones_config=[
                {"name": "Crane_Zone", "polygon": [[0, 0], [300, 0], [300, 300], [0, 300]]}
            ],
        )
        assert started is True

        time.sleep(0.3)

        # Query safety status
        status = service.query_safety_status("cam_crane_01")
        assert status["camera_id"] == "cam_crane_01"
        assert status["is_online"] is True
        assert "timestamp" in status

        # Generate daily report
        report = service.generate_daily_safety_report("2026-09-25")
        assert report["date"] == "2026-09-25"
        assert report["total_violations"] >= 2
        assert ViolationType.DANGER_ZONE_INTRUSION.value in report["by_type"]
        assert ViolationSeverity.CRITICAL.value in report["by_severity"]
        assert report["by_camera"]["cam_crane_01"] >= 2

        # Stop monitoring
        stopped = service.stop_monitoring("cam_crane_01")
        assert stopped is True

        offline_status = service.query_safety_status("cam_crane_01")
        assert offline_status["is_online"] is False
