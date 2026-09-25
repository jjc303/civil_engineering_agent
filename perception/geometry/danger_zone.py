from __future__ import annotations

import json
from pathlib import Path
from typing import List, Tuple, Union
import cv2
import numpy as np

from perception.schemas.detection import BoundingBox, DangerZone


def point_in_polygon_cv2(polygon: Union[np.ndarray, List[Tuple[float, float]]], pt: Tuple[float, float]) -> bool:
    """
    Determines if point pt is inside or on the boundary of polygon using OpenCV C++ implementation.
    :param polygon: List of (x, y) or np.ndarray of shape (N, 2) or (N, 1, 2)
    :param pt: (x, y) coordinates
    :return: True if point is inside or on the polygon contour, False otherwise
    """
    if not isinstance(polygon, np.ndarray):
        contour = np.array(polygon, dtype=np.int32).reshape((-1, 1, 2))
    elif polygon.ndim == 2:
        contour = polygon.reshape((-1, 1, 2)).astype(np.int32)
    else:
        contour = polygon.astype(np.int32)

    # measureDist=False: +1 inside, 0 on edge, -1 outside
    res = cv2.pointPolygonTest(contour, (float(pt[0]), float(pt[1])), measureDist=False)
    return res >= 0


def person_in_danger_zone(
    bbox: BoundingBox,
    polygon: Union[np.ndarray, List[Tuple[float, float]]],
) -> bool:
    """
    High-precision spatial intrusion test based on feet ground contact points.
    Evaluates:
      1) Primary point: bottom-center ground contact point (cx, y2)
      2) Secondary auxiliary points: bottom 1/4 and 3/4 edge points
    An intrusion is confirmed if the primary point is inside, or at least 2 contact points are inside.
    """
    w = bbox.width
    y2 = bbox.y2

    primary_pt = (bbox.x1 + 0.5 * w, y2)
    left_quarter_pt = (bbox.x1 + 0.25 * w, y2)
    right_quarter_pt = (bbox.x1 + 0.75 * w, y2)

    pts = [primary_pt, left_quarter_pt, right_quarter_pt]
    hits = sum(1 for p in pts if point_in_polygon_cv2(polygon, p))

    # If primary ground point is inside, or 2 out of 3 feet points are inside
    return hits >= 2 or point_in_polygon_cv2(polygon, primary_pt)


def map_ui_to_raw_coords(
    ui_pt: Tuple[float, float],
    raw_size: Tuple[int, int],
    ui_size: Tuple[int, int],
) -> Tuple[float, float]:
    """
    Maps viewport UI pixel coordinates back to the original video frame coordinate system.
    Accounts for Aspect-Ratio / Letterbox scaling with horizontal/vertical black bars (padding).
    :param ui_pt: (x_ui, y_ui) in UI widget pixel coordinates
    :param raw_size: (W_raw, H_raw) original video resolution
    :param ui_size: (W_ui, H_ui) UI video widget dimensions
    :return: (x_raw, y_raw) in video frame pixel coordinates
    """
    w_raw, h_raw = raw_size
    w_ui, h_ui = ui_size

    scale = min(w_ui / w_raw, h_ui / h_raw)
    pad_x = (w_ui - w_raw * scale) / 2.0
    pad_y = (h_ui - h_raw * scale) / 2.0

    x_raw = (ui_pt[0] - pad_x) / scale
    y_raw = (ui_pt[1] - pad_y) / scale

    # Clamp to valid range
    x_raw = max(0.0, min(float(w_raw - 1), x_raw))
    y_raw = max(0.0, min(float(h_raw - 1), y_raw))

    return (x_raw, y_raw)


def map_raw_to_ui_coords(
    raw_pt: Tuple[float, float],
    raw_size: Tuple[int, int],
    ui_size: Tuple[int, int],
) -> Tuple[float, float]:
    """
    Maps original video frame pixel coordinates to viewport UI pixel coordinates.
    """
    w_raw, h_raw = raw_size
    w_ui, h_ui = ui_size

    scale = min(w_ui / w_raw, h_ui / h_raw)
    pad_x = (w_ui - w_raw * scale) / 2.0
    pad_y = (h_ui - h_raw * scale) / 2.0

    x_ui = raw_pt[0] * scale + pad_x
    y_ui = raw_pt[1] * scale + pad_y

    return (x_ui, y_ui)


def load_danger_zones_from_json(json_path: Union[str, Path]) -> List[DangerZone]:
    """
    Loads danger zone polygon definitions from JSON files.
    Supports:
      1) Modern DangerZone list format (e.g. default_danger_zones.json)
      2) Modern dict container format (e.g. {"zones": [...]})
      3) Legacy annotation JSON format (e.g. outputs.object[].polygon.{x1, y1, ...})
    """
    p = Path(json_path)
    if not p.is_file():
        return []

    with open(p, "r", encoding="utf-8") as f:
        data = json.load(f)

    zones: List[DangerZone] = []

    # Format 1: Direct list of DangerZone dicts (e.g. default_danger_zones.json)
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict) and "polygon" in item:
                pts = [(float(pt[0]), float(pt[1])) for pt in item["polygon"]]
                item_dict = dict(item)
                item_dict["polygon"] = pts
                zones.append(DangerZone(**item_dict))
            elif isinstance(item, DangerZone):
                zones.append(item)
        return zones

    if not isinstance(data, dict):
        return []

    # Format 2: Dict containing zones list, e.g. {"zones": [...]} or {"danger_zones": [...]}
    zone_list = data.get("zones") or data.get("danger_zones")
    if isinstance(zone_list, list):
        for item in zone_list:
            if isinstance(item, dict) and "polygon" in item:
                pts = [(float(pt[0]), float(pt[1])) for pt in item["polygon"]]
                item_dict = dict(item)
                item_dict["polygon"] = pts
                zones.append(DangerZone(**item_dict))
        return zones

    # Format 3: Legacy annotation format: outputs.object[].polygon.{x1, y1, ...}
    outputs = data.get("outputs", {})
    objects = outputs.get("object", [])

    for idx, obj in enumerate(objects):
        poly_data = obj.get("polygon", {})
        if not poly_data:
            continue

        num_pts = len(poly_data) // 2
        pts: List[Tuple[float, float]] = []
        for i in range(1, num_pts + 1):
            kx = f"x{i}"
            ky = f"y{i}"
            if kx in poly_data and ky in poly_data:
                pts.append((float(poly_data[kx]), float(poly_data[ky])))

        if len(pts) >= 3:
            zone_name = obj.get("name", f"danger_zone_{idx+1}")
            zones.append(DangerZone(name=zone_name, polygon=pts))

    return zones
