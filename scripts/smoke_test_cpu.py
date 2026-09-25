#!/usr/bin/env python3
"""
CPU Smoke Test Script for Civil Engineering Agent Perception System.
Validates the full perception pipeline on CPU:
- Image loading & preprocessing
- Detector interface
- Spatial danger zone intrusion (feet contact point)
- Multi-object tracking (ByteTrack)
- Output metrics and latency
"""

import sys
import time
from pathlib import Path
import cv2

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from perception.detectors.base import MockDetector
from perception.geometry.danger_zone import (
    load_danger_zones_from_json,
    person_in_danger_zone,
)
from perception.tracking.byte_tracker import BYTETracker


def run_cpu_smoke_test():
    print("=" * 60)
    print("Starting Civil Engineering Agent Perception CPU Smoke Test...")
    print("=" * 60)

    fixtures_dir = ROOT / "tests" / "fixtures"
    image_path = fixtures_dir / "sample_site.jpg"
    json_path = fixtures_dir / "sample_site.json"

    assert image_path.is_file(), f"Missing test fixture: {image_path}"
    assert json_path.is_file(), f"Missing test fixture: {json_path}"

    # 1. Load image
    t_start = time.monotonic()
    img = cv2.imread(str(image_path))
    assert img is not None, "Failed to load sample image"
    h, w, c = img.shape
    print(f"[OK] Sample image loaded: {w}x{h}, {c} channels")

    # 2. Load Danger Zones
    zones = load_danger_zones_from_json(json_path)
    assert len(zones) > 0, "No danger zones found in sample JSON"
    print(f"[OK] Danger zones loaded: {len(zones)} zones (e.g., '{zones[0].name}' with {len(zones[0].polygon)} vertices)")

    # 3. Detector execution (Prioritize helmet_head_person_m.pt as primary)
    primary_weight = ROOT / "perception" / "weights" / "helmet_head_person_m.pt"
    secondary_weight = ROOT / "perception" / "weights" / "helmet_head_person_s.pt"

    if primary_weight.is_file():
        from perception.detectors.legacy_yolo_adapter import LegacyYOLOv5Adapter
        detector = LegacyYOLOv5Adapter(str(primary_weight), device="cpu")
        print(f"[OK] Using PRIMARY business weight: {primary_weight.name}")
    elif secondary_weight.is_file():
        from perception.detectors.legacy_yolo_adapter import LegacyYOLOv5Adapter
        detector = LegacyYOLOv5Adapter(str(secondary_weight), device="cpu")
        print(f"[OK] Using secondary business weight: {secondary_weight.name}")
    else:
        detector = MockDetector()
        detector.load_model("mock_weights.pt", device="cpu")
        print("[INFO] Real weight not found, falling back to MockDetector")

    det_result = detector.detect(img, conf_threshold=0.4)
    print(f"[OK] Detector executed in {det_result.inference_time_ms:.2f} ms with {len(det_result.boxes)} detections")

    # 4. ByteTrack tracking
    tracker = BYTETracker()
    person_boxes = [b for b in det_result.boxes if b.class_name == "person"]
    tracked_persons = tracker.update(person_boxes)
    print(f"[OK] ByteTracker updated: {len(tracked_persons)} active tracked persons")

    # 5. Intrusion detection
    for person in tracked_persons:
        for zone in zones:
            is_inside = person_in_danger_zone(person.bbox, zone.polygon)
            person.is_in_danger_zone = is_inside
            if is_inside:
                person.danger_zone_name = zone.name
                print(f"[ALERT] Worker ID {person.track_id} detected inside danger zone: '{zone.name}'!")

    t_total = (time.monotonic() - t_start) * 1000.0
    print(f"[OK] Total pipeline CPU processing time: {t_total:.2f} ms")
    print("=" * 60)
    print("ALL CPU SMOKE TESTS PASSED SUCCESSFULLY!")
    print("=" * 60)
    return 0


if __name__ == "__main__":
    sys.exit(run_cpu_smoke_test())
