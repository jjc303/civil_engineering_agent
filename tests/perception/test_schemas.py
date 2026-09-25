import pytest
from perception.schemas.detection import (
    BoundingBox,
    DetectionResult,
    TrackedPerson,
    DangerZone,
    ViolationEvent,
    ViolationType,
    ViolationSeverity,
)


def test_bounding_box_properties():
    box = BoundingBox(
        x1=100.0,
        y1=50.0,
        x2=200.0,
        y2=300.0,
        conf=0.95,
        class_id=0,
        class_name="person",
    )
    assert box.width == 100.0
    assert box.height == 250.0
    assert box.center == (150.0, 175.0)
    assert box.feet_point == (150.0, 300.0)


def test_detection_result_serialization():
    box = BoundingBox(
        x1=10.0,
        y1=20.0,
        x2=50.0,
        y2=80.0,
        conf=0.85,
        class_id=2,
        class_name="helmet",
    )
    res = DetectionResult(frame_id=1, boxes=[box], inference_time_ms=12.5)

    data = res.model_dump()
    assert data["frame_id"] == 1
    assert len(data["boxes"]) == 1
    assert data["boxes"][0]["class_name"] == "helmet"

    restored = DetectionResult.model_validate(data)
    assert restored.boxes[0].conf == 0.85


def test_violation_event_creation():
    event = ViolationEvent(
        event_uuid="evt-001",
        track_id=42,
        camera_id="cam_main",
        violation_type=ViolationType.DANGER_ZONE_INTRUSION,
        severity=ViolationSeverity.CRITICAL,
        zone_name="Crane_Lift_Zone",
        duration_seconds=6.5,
    )
    assert event.severity == ViolationSeverity.CRITICAL
    assert event.track_id == 42
