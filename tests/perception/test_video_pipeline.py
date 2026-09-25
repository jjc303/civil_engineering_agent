from pathlib import Path
import json
import cv2
import pytest

from perception.schemas.detection import BoundingBox
from perception.geometry.danger_zone import point_in_polygon_cv2
from perception.tracking.byte_tracker import BYTETracker


PROJECT_ROOT = Path(__file__).resolve().parents[2]
FIXTURES_DIR = PROJECT_ROOT / "tests" / "fixtures"


def test_sample_walk_video_ground_truth_consistency():
    video_path = FIXTURES_DIR / "sample_walk.mp4"
    gt_path = FIXTURES_DIR / "ground_truth.json"

    assert video_path.is_file(), "sample_walk.mp4 missing"
    assert gt_path.is_file(), "ground_truth.json missing"

    with open(gt_path, "r", encoding="utf-8") as f:
        gt_data = json.load(f)

    cap = cv2.VideoCapture(str(video_path))
    assert cap.isOpened(), "Failed to open sample_walk.mp4"

    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    assert frame_count == gt_data["metadata"]["total_frames"]

    danger_polygon = gt_data["danger_zones"][0]["polygon"]
    expected_entry_frame = gt_data["events"]["entry_frame"]

    tracker = BYTETracker()
    detected_entry_frame = None

    for f_idx in range(frame_count):
        ret, frame = cap.read()
        assert ret, f"Failed to read frame {f_idx}"

        gt_frame = gt_data["frame_annotations"][f_idx]
        bx1, by1, bx2, by2 = gt_frame["worker_bbox"]

        # Feed ground truth detection box to tracker to verify tracking pipeline
        box = BoundingBox(
            x1=float(bx1),
            y1=float(by1),
            x2=float(bx2),
            y2=float(by2),
            conf=0.95,
            class_id=0,
            class_name="person",
        )
        tracks = tracker.update([box])
        assert len(tracks) == 1, f"Frame {f_idx} failed to track single worker"

        # Check feet contact point in polygon
        feet_pt = tracks[0].feet_point
        is_inside = point_in_polygon_cv2(danger_polygon, feet_pt)
        assert is_inside == gt_frame["in_danger_zone"], f"Frame {f_idx} intrusion state mismatch"

        if is_inside and detected_entry_frame is None:
            detected_entry_frame = f_idx

    cap.release()

    assert detected_entry_frame == expected_entry_frame, (
        f"Detected entry frame {detected_entry_frame} != expected {expected_entry_frame}"
    )
