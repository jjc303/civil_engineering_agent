from pathlib import Path
import tempfile
import numpy as np
import pytest

from perception.schemas.detection import (
    BoundingBox,
    ViolationEvent,
    ViolationSeverity,
    ViolationType,
)
from perception.storage.event_store import EventStore


def test_event_store_save_and_query():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "events.db"
        store = EventStore(db_path=db_path)

        ev1 = ViolationEvent(
            event_uuid="ev-1001",
            track_id=1,
            camera_id="cam_main",
            violation_type=ViolationType.DANGER_ZONE_INTRUSION,
            severity=ViolationSeverity.WARNING,
            zone_name="Crane_Area",
            start_time=100.0,
            duration_seconds=2.5,
        )

        ev2 = ViolationEvent(
            event_uuid="ev-1002",
            track_id=2,
            camera_id="cam_main",
            violation_type=ViolationType.NO_HELMET,
            severity=ViolationSeverity.WARNING,
            start_time=105.0,
            duration_seconds=5.0,
        )

        store.save_event(ev1)
        store.save_event(ev2)

        # Query all
        results = store.query_events()
        assert len(results) == 2

        # Query by violation type
        helmet_events = store.query_events(violation_type=ViolationType.NO_HELMET)
        assert len(helmet_events) == 1
        assert helmet_events[0].event_uuid == "ev-1002"

        # Close event
        closed = store.close_event(event_uuid="ev-1001", end_time=110.0, duration_seconds=10.0)
        assert closed is True

        ev1_reloaded = store.get_event_by_id("ev-1001")
        assert ev1_reloaded is not None
        assert ev1_reloaded.end_time == 110.0
        assert ev1_reloaded.duration_seconds == 10.0

        # Statistics
        stats = store.get_statistics()
        assert stats["total_violations"] == 2
        assert stats["by_type"][ViolationType.DANGER_ZONE_INTRUSION.value] == 1
        assert stats["by_type"][ViolationType.NO_HELMET.value] == 1


def test_event_store_snapshot_archiving():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "events.db"
        snapshot_dir = Path(tmp_dir) / "snapshots"
        store = EventStore(db_path=db_path, snapshot_dir=snapshot_dir)

        fake_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        person_box = BoundingBox(
            x1=100.0, y1=100.0, x2=200.0, y2=300.0,
            conf=0.9, class_id=0, class_name="person",
        )
        zone_polygon = [(50.0, 50.0), (300.0, 50.0), (300.0, 400.0), (50.0, 400.0)]

        event = ViolationEvent(
            event_uuid="ev-snap-01",
            track_id=42,
            camera_id="cam_gate",
            violation_type=ViolationType.DWELL_TIMEOUT,
            severity=ViolationSeverity.CRITICAL,
            zone_name="Excavator_Zone",
            start_time=50.0,
            duration_seconds=6.2,
        )

        saved_event = store.save_event(
            event=event,
            frame=fake_frame,
            person_bbox=person_box,
            zone_polygon=zone_polygon,
        )

        assert saved_event.snapshot_path is not None
        full_snap_path = snapshot_dir / saved_event.snapshot_path
        assert full_snap_path.is_file(), f"Snapshot file {full_snap_path} was not created"
        assert full_snap_path.stat().st_size > 0
