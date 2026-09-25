import pytest
from perception.geometry.topology import (
    HelmetCompliance,
    PersonTopologyResult,
    match_person_head_helmet,
)
from perception.schemas.detection import BoundingBox


def test_topology_single_person_with_helmet():
    # Worker at (100, 100) to (200, 300) -> height 200, width 100
    # Head region is top 35%: y: 100 ~ 170
    person = BoundingBox(
        x1=100.0, y1=100.0, x2=200.0, y2=300.0,
        conf=0.9, class_id=0, class_name="person",
    )
    helmet = BoundingBox(
        x1=120.0, y1=90.0, x2=180.0, y2=140.0,
        conf=0.95, class_id=2, class_name="helmet",
    )

    results = match_person_head_helmet([person, helmet])
    assert len(results) == 1
    res = results[0]
    assert res.compliance == HelmetCompliance.HELMETED
    assert res.has_helmet is True
    assert res.helmet_box is not None
    assert res.helmet_box.class_name == "helmet"


def test_topology_single_person_with_bare_head():
    person = BoundingBox(
        x1=100.0, y1=100.0, x2=200.0, y2=300.0,
        conf=0.9, class_id=0, class_name="person",
    )
    bare_head = BoundingBox(
        x1=125.0, y1=100.0, x2=175.0, y2=150.0,
        conf=0.88, class_id=1, class_name="head",
    )

    results = match_person_head_helmet([person, bare_head])
    assert len(results) == 1
    res = results[0]
    assert res.compliance == HelmetCompliance.UNHELMETED
    assert res.has_helmet is False
    assert res.head_box is not None
    assert res.helmet_box is None


def test_topology_multiple_persons_and_helmets_bipartite():
    # Worker 1 at x=100~200, Worker 2 at x=400~500
    p1 = BoundingBox(x1=100.0, y1=100.0, x2=200.0, y2=300.0, conf=0.9, class_id=0, class_name="person")
    p2 = BoundingBox(x1=400.0, y1=100.0, x2=500.0, y2=300.0, conf=0.9, class_id=0, class_name="person")

    # Helmet 1 on Worker 1
    h1 = BoundingBox(x1=120.0, y1=90.0, x2=180.0, y2=140.0, conf=0.95, class_id=2, class_name="helmet")
    # Bare head on Worker 2
    head2 = BoundingBox(x1=425.0, y1=100.0, x2=475.0, y2=150.0, conf=0.85, class_id=1, class_name="head")
    # Stray helmet on the ground at x=800~850 (nowhere near any person)
    stray_h = BoundingBox(x1=800.0, y1=500.0, x2=850.0, y2=550.0, conf=0.7, class_id=2, class_name="helmet")

    results = match_person_head_helmet([p1, p2, h1, head2, stray_h])
    assert len(results) == 2

    res1 = next(r for r in results if r.person_box.x1 == 100.0)
    assert res1.compliance == HelmetCompliance.HELMETED
    assert res1.has_helmet is True

    res2 = next(r for r in results if r.person_box.x1 == 400.0)
    assert res2.compliance == HelmetCompliance.UNHELMETED
    assert res2.has_helmet is False


def test_topology_no_head_or_helmet_detected():
    person = BoundingBox(
        x1=100.0, y1=100.0, x2=200.0, y2=300.0,
        conf=0.9, class_id=0, class_name="person",
    )
    results = match_person_head_helmet([person])
    assert len(results) == 1
    assert results[0].compliance == HelmetCompliance.UNKNOWN
    assert results[0].has_helmet is False
