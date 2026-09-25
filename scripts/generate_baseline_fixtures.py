#!/usr/bin/env python3
"""
Generates deterministic baseline artifacts and fixtures for Phase 0 sign-off:
1. tests/fixtures/baseline_output.jpg: Visual inference result with bounding boxes,
   feet contact points, and danger zone polygon.
2. tests/fixtures/sample_walk.mp4: 5-second 25fps test video of a worker walking into a danger zone.
3. tests/fixtures/ground_truth.json: Ground-truth annotations and temporal event timestamps.
"""

import json
import sys
import time
from pathlib import Path
import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from perception.detectors.legacy_yolo_adapter import LegacyYOLOv5Adapter
from perception.geometry.danger_zone import (
    load_danger_zones_from_json,
    person_in_danger_zone,
    point_in_polygon_cv2,
)


def generate_baseline_image():
    print("[1/3] Generating baseline output image (tests/fixtures/baseline_output.jpg)...")
    img_path = ROOT / "tests" / "fixtures" / "sample_site.jpg"
    json_path = ROOT / "tests" / "fixtures" / "sample_site.json"
    weight_path = ROOT / "perception" / "weights" / "helmet_head_person_m.pt"

    img = cv2.imread(str(img_path))
    assert img is not None, "Failed to read sample_site.jpg"
    zones = load_danger_zones_from_json(json_path)

    adapter = LegacyYOLOv5Adapter(str(weight_path), device="cpu")
    det_result = adapter.detect(img, conf_threshold=0.4)

    output_img = img.copy()

    # Draw danger zones
    for zone in zones:
        pts = np.array(zone.polygon, dtype=np.int32).reshape((-1, 1, 2))
        cv2.polylines(output_img, [pts], isClosed=True, color=(0, 0, 255), thickness=3)
        # Put zone label
        cx, cy = int(zone.polygon[0][0]), int(zone.polygon[0][1])
        cv2.putText(
            output_img,
            f"ZONE: {zone.name}",
            (cx, cy - 10),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 0, 255),
            2,
        )

    # Draw detections
    for box in det_result.boxes:
        x1, y1, x2, y2 = int(box.x1), int(box.y1), int(box.x2), int(box.y2)

        if box.class_name == "person":
            is_inside = any(person_in_danger_zone(box, z.polygon) for z in zones)
            color = (0, 0, 255) if is_inside else (0, 255, 0)
            tag = "INTRUSION: person" if is_inside else "person"

            # Draw feet point
            fx, fy = int(box.feet_point[0]), int(box.feet_point[1])
            cv2.circle(output_img, (fx, fy), 6, (0, 255, 255), -1)
        elif box.class_name == "helmet":
            color = (255, 128, 0)
            tag = "helmet"
        else:
            color = (0, 165, 255)
            tag = "head"

        cv2.rectangle(output_img, (x1, y1), (x2, y2), color, 2)
        label_text = f"{tag} {box.conf:.2f}"
        cv2.putText(
            output_img,
            label_text,
            (x1, max(15, y1 - 8)),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.5,
            color,
            2,
        )

    out_file = ROOT / "tests" / "fixtures" / "baseline_output.jpg"
    cv2.imwrite(str(out_file), output_img)
    print(f"    -> Saved baseline image to: {out_file}")


def generate_sample_walk_video_and_ground_truth():
    print("[2/3] Generating sample walk video (tests/fixtures/sample_walk.mp4)...")
    fps = 25
    duration_sec = 5
    total_frames = fps * duration_sec
    w, h = 1280, 720

    out_video_path = ROOT / "tests" / "fixtures" / "sample_walk.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(out_video_path), fourcc, fps, (w, h))

    # Define Danger Zone: Polygon from (700, 200) to (1200, 650)
    danger_polygon = [
        (700.0, 200.0),
        (1200.0, 200.0),
        (1200.0, 650.0),
        (700.0, 650.0),
    ]

    # Worker starts at x=200, walks toward x=950 (crosses into danger zone at x=700)
    # y position is around 400
    start_x = 200.0
    end_x = 950.0
    y = 400.0
    box_w = 80.0
    box_h = 180.0

    gt_frames = []
    entry_frame = None

    for f_idx in range(total_frames):
        alpha = f_idx / float(total_frames - 1)
        cur_x = start_x + (end_x - start_x) * alpha
        feet_x = cur_x + box_w / 2.0
        feet_y = y + box_h
        pts_in_zone = point_in_polygon_cv2(danger_polygon, (feet_x, feet_y))

        if pts_in_zone and entry_frame is None:
            entry_frame = f_idx

        # Render frame
        frame = np.full((h, w, 3), 40, dtype=np.uint8)

        # Draw grid floor pattern
        for gy in range(0, h, 60):
            cv2.line(frame, (0, gy), (w, gy), (55, 55, 55), 1)
        for gx in range(0, w, 60):
            cv2.line(frame, (gx, 0), (gx, h), (55, 55, 55), 1)

        # Draw danger zone polygon
        poly_np = np.array(danger_polygon, dtype=np.int32).reshape((-1, 1, 2))
        cv2.polylines(frame, [poly_np], isClosed=True, color=(0, 0, 220), thickness=3)
        cv2.putText(
            frame,
            "DANGER ZONE (EXCLUSION AREA)",
            (710, 230),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (0, 0, 255),
            2,
        )

        # Draw worker body (person rectangle)
        bx1, by1 = int(cur_x), int(y)
        bx2, by2 = int(cur_x + box_w), int(y + box_h)
        worker_color = (0, 0, 255) if pts_in_zone else (0, 200, 0)
        cv2.rectangle(frame, (bx1, by1), (bx2, by2), worker_color, -1)
        cv2.rectangle(frame, (bx1, by1), (bx2, by2), (255, 255, 255), 2)

        # Draw helmet on worker head
        hx1, hy1 = bx1 + 10, by1 - 25
        hx2, hy2 = bx2 - 10, by1
        cv2.rectangle(frame, (hx1, hy1), (hx2, hy2), (0, 255, 255), -1)

        # Frame stamp
        cv2.putText(
            frame,
            f"Frame: {f_idx} | Time: {f_idx/fps:.2f}s | Worker X: {cur_x:.1f}",
            (30, 40),
            cv2.FONT_HERSHEY_SIMPLEX,
            0.7,
            (255, 255, 255),
            2,
        )

        writer.write(frame)

        gt_frames.append({
            "frame_id": f_idx,
            "timestamp": round(f_idx / fps, 3),
            "worker_bbox": [bx1, by1, bx2, by2],
            "feet_point": [feet_x, feet_y],
            "in_danger_zone": pts_in_zone,
        })

    writer.release()
    print(f"    -> Saved sample video to: {out_video_path}")

    # Generate Ground Truth JSON
    print("[3/3] Generating ground truth annotation JSON (tests/fixtures/ground_truth.json)...")
    gt_data = {
        "metadata": {
            "video_path": "tests/fixtures/sample_walk.mp4",
            "fps": fps,
            "total_frames": total_frames,
            "duration_seconds": duration_sec,
            "resolution": [w, h],
        },
        "danger_zones": [
            {
                "name": "EXCLUSION_AREA",
                "polygon": danger_polygon,
            }
        ],
        "events": {
            "entry_frame": entry_frame,
            "entry_timestamp_sec": round(entry_frame / fps, 3) if entry_frame else None,
            "expected_violation_duration_sec": round((total_frames - entry_frame) / fps, 3) if entry_frame else 0,
        },
        "frame_annotations": gt_frames,
    }

    gt_file = ROOT / "tests" / "fixtures" / "ground_truth.json"
    with open(gt_file, "w", encoding="utf-8") as f:
        json.dump(gt_data, f, indent=2)
    print(f"    -> Saved ground truth to: {gt_file}")
    print(f"    -> Worker enters danger zone at Frame {entry_frame} ({entry_frame/fps:.2f}s)")


if __name__ == "__main__":
    generate_baseline_image()
    generate_sample_walk_video_and_ground_truth()
    print("\nALL BASELINE FIXTURES SUCCESSFULLY GENERATED!")
