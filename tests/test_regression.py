from pathlib import Path
import cv2
import pytest

from perception.detectors.legacy_yolo_adapter import LegacyYOLOv5Adapter
from perception.detectors.ultralytics_detector import UltralyticsDetector
from perception.geometry.danger_zone import load_danger_zones_from_json, person_in_danger_zone
from perception.schemas.detection import DetectionResult

FIXTURES_DIR = Path(__file__).parent / "fixtures"
WEIGHTS_DIR = Path(__file__).parent.parent / "perception" / "weights"


def test_legacy_yolo_adapter_regression():
    weight_path = WEIGHTS_DIR / "helmet_head_person_m.pt"
    if not weight_path.is_file():
        weight_path = WEIGHTS_DIR / "helmet_head_person_s.pt"
    assert weight_path.is_file(), f"No business weights found in {WEIGHTS_DIR}"

    adapter = LegacyYOLOv5Adapter(str(weight_path), device="cpu")
    img_path = FIXTURES_DIR / "sample_site.jpg"
    img = cv2.imread(str(img_path))
    assert img is not None

    res = adapter.detect(img, conf_threshold=0.4)
    assert isinstance(res, DetectionResult)
    assert len(res.boxes) >= 2, f"Expected at least 2 detections, got {len(res.boxes)}"

    class_names = [b.class_name for b in res.boxes]
    assert "person" in class_names, "Expected 'person' class in legacy detection"
    assert "helmet" in class_names, "Expected 'helmet' class in legacy detection"

    # Verify spatial intrusion logic
    zones = load_danger_zones_from_json(FIXTURES_DIR / "sample_site.json")
    assert len(zones) > 0
    danger_polygon = zones[0].polygon

    person_boxes = [b for b in res.boxes if b.class_name == "person"]
    intrusions = [person_in_danger_zone(p, danger_polygon) for p in person_boxes]
    assert any(intrusions), "Expected at least 1 person inside danger zone"


def test_ultralytics_detector_regression():
    weight_path = WEIGHTS_DIR / "yolov8n.pt"
    assert weight_path.is_file(), f"Ultralytics weight not found at {weight_path}"

    detector = UltralyticsDetector(str(weight_path), device="cpu")
    img_path = FIXTURES_DIR / "sample_site.jpg"
    img = cv2.imread(str(img_path))
    assert img is not None

    res = detector.detect(img, conf_threshold=0.3)
    assert isinstance(res, DetectionResult)
    assert len(res.boxes) > 0, "Expected at least 1 detection from UltralyticsDetector"

    class_names = [b.class_name for b in res.boxes]
    assert "person" in class_names, "Expected 'person' detected by Ultralytics on sample site"
