import json
from pathlib import Path
import pytest
from perception.geometry.danger_zone import (
    point_in_polygon_cv2,
    person_in_danger_zone,
    map_ui_to_raw_coords,
    map_raw_to_ui_coords,
    load_danger_zones_from_json,
)
from perception.schemas.detection import BoundingBox


def test_point_in_polygon():
    # Square polygon from (100, 100) to (300, 300)
    polygon = [(100.0, 100.0), (300.0, 100.0), (300.0, 300.0), (100.0, 300.0)]

    # Inside point
    assert point_in_polygon_cv2(polygon, (200.0, 200.0)) is True

    # Edge point
    assert point_in_polygon_cv2(polygon, (100.0, 150.0)) is True

    # Outside point
    assert point_in_polygon_cv2(polygon, (50.0, 50.0)) is False
    assert point_in_polygon_cv2(polygon, (400.0, 200.0)) is False


def test_person_in_danger_zone_feet_detection():
    # Square danger zone: [100, 100] to [300, 300]
    polygon = [(100.0, 100.0), (300.0, 100.0), (300.0, 300.0), (100.0, 300.0)]

    # Person with feet (bottom center) inside danger zone, but upper body outside
    # Box: x1=150, y1=50, x2=250, y2=150 (feet at 200, 150 -> inside)
    intruding_person = BoundingBox(
        x1=150.0,
        y1=50.0,
        x2=250.0,
        y2=150.0,
        conf=0.9,
        class_id=0,
        class_name="person",
    )
    assert person_in_danger_zone(intruding_person, polygon) is True

    # Person completely outside
    safe_person = BoundingBox(
        x1=400.0,
        y1=50.0,
        x2=450.0,
        y2=150.0,
        conf=0.9,
        class_id=0,
        class_name="person",
    )
    assert person_in_danger_zone(safe_person, polygon) is False


def test_gui_coordinate_mapping_roundtrip():
    # Raw video 1920x1080, UI video widget 960x540
    raw_size = (1920, 1080)
    ui_size = (960, 540)

    test_points = [(100.0, 200.0), (500.0, 300.0), (900.0, 500.0)]

    for pt in test_points:
        raw_pt = map_ui_to_raw_coords(pt, raw_size, ui_size)
        restored_ui_pt = map_raw_to_ui_coords(raw_pt, raw_size, ui_size)

        # DoD: round-trip error <= 1 pixel
        err_x = abs(round(restored_ui_pt[0]) - round(pt[0]))
        err_y = abs(round(restored_ui_pt[1]) - round(pt[1]))
        assert err_x <= 1, f"X roundtrip error {err_x} > 1 for {pt}"
        assert err_y <= 1, f"Y roundtrip error {err_y} > 1 for {pt}"


def test_load_danger_zones_from_json():
    json_path = Path(__file__).parent / "fixtures" / "sample_site.json"
    zones = load_danger_zones_from_json(json_path)

    assert len(zones) >= 1
    assert zones[0].name == "dangerous"
    assert len(zones[0].polygon) == 9  # 1.json has 9 vertices


def test_load_danger_zones_from_modern_config():
    # Test loading modern default_danger_zones.json (list format)
    cfg_path = Path(__file__).parent.parent / "perception" / "configs" / "default_danger_zones.json"
    zones = load_danger_zones_from_json(cfg_path)

    assert len(zones) == 1
    assert zones[0].name == "Crane_Operational_Zone"
    assert len(zones[0].polygon) == 9
    assert zones[0].alarm_dwell_threshold_seconds == 5.0
    assert zones[0].enabled is True


def test_load_danger_zones_from_dict_container(tmp_path):
    # Test loading dict container format {"zones": [...]}
    test_json = tmp_path / "test_zones.json"
    test_json.write_text(
        json.dumps({
            "zones": [
                {
                    "name": "Scaffold_Zone",
                    "polygon": [[10.0, 10.0], [50.0, 10.0], [50.0, 50.0], [10.0, 50.0]],
                    "alarm_dwell_threshold_seconds": 3.0,
                    "enabled": True,
                }
            ]
        }),
        encoding="utf-8",
    )
    zones = load_danger_zones_from_json(test_json)
    assert len(zones) == 1
    assert zones[0].name == "Scaffold_Zone"
    assert len(zones[0].polygon) == 4
    assert zones[0].alarm_dwell_threshold_seconds == 3.0
