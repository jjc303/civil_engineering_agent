import pytest
from perception.schemas.detection import (
    BoundingBox,
    DangerZone,
    TrackedPerson,
    ViolationSeverity,
    ViolationType,
)
from perception.tracking.state_machine import (
    HelmetComplianceTracker,
    PersonZoneTracker,
    WorkerSafetyMonitor,
    ZoneIntrusionState,
)


def _make_tracked_person(track_id: int, cx: float, cy: float, has_helmet: bool = True) -> TrackedPerson:
    # 50x100 box with feet at (cx, cy)
    bbox = BoundingBox(
        x1=cx - 25.0,
        y1=cy - 100.0,
        x2=cx + 25.0,
        y2=cy,
        conf=0.9,
        class_id=0,
        class_name="person",
        has_helmet=has_helmet,
    )
    return TrackedPerson(
        track_id=track_id,
        bbox=bbox,
        feet_point=(cx, cy),
        has_helmet=has_helmet,
    )


def test_zone_tracker_debounce_and_dwell_timeout():
    # Danger zone square: (100, 100) to (300, 300)
    tracker = PersonZoneTracker(track_id=1, zone_name="Crane_Area", dwell_threshold=5.0)

    # Frame 1: inside (raw inside = True)
    ev_new, ev_closed = tracker.update(is_inside_raw=True, current_time=0.0, enter_debounce_frames=3)
    assert tracker.state == ZoneIntrusionState.PENDING_ENTER
    assert ev_new is None

    # Frame 2: inside
    ev_new, ev_closed = tracker.update(is_inside_raw=True, current_time=0.1, enter_debounce_frames=3)
    assert tracker.state == ZoneIntrusionState.PENDING_ENTER
    assert ev_new is None

    # Frame 3: inside -> meets enter_debounce_frames=3 -> INTRUSION
    ev_new, ev_closed = tracker.update(is_inside_raw=True, current_time=0.2, enter_debounce_frames=3)
    assert tracker.state == ZoneIntrusionState.INTRUSION
    assert ev_new is not None
    assert ev_new.violation_type == ViolationType.DANGER_ZONE_INTRUSION
    assert ev_new.severity == ViolationSeverity.WARNING

    # Advance time to 4.5 seconds (still < 5.0 threshold)
    ev_new, ev_closed = tracker.update(is_inside_raw=True, current_time=4.5, enter_debounce_frames=3)
    assert tracker.state == ZoneIntrusionState.INTRUSION
    assert ev_new is None
    assert tracker.dwell_seconds == pytest.approx(4.3, 0.05)

    # Advance time to 5.2 seconds (>= 5.0 threshold) -> escalates to DWELL_TIMEOUT
    ev_new, ev_closed = tracker.update(is_inside_raw=True, current_time=5.3, enter_debounce_frames=3)
    assert tracker.state == ZoneIntrusionState.DWELL_TIMEOUT
    assert ev_new is not None
    assert ev_new.violation_type == ViolationType.DWELL_TIMEOUT
    assert ev_new.severity == ViolationSeverity.CRITICAL

    # Step outside for 1 frame -> PENDING_EXIT (not yet closed due to exit debounce)
    ev_new, ev_closed = tracker.update(is_inside_raw=False, current_time=5.4, exit_debounce_frames=3)
    assert tracker.state == ZoneIntrusionState.PENDING_EXIT
    assert ev_closed is None

    # Frame 2 outside
    ev_new, ev_closed = tracker.update(is_inside_raw=False, current_time=5.5, exit_debounce_frames=3)
    assert tracker.state == ZoneIntrusionState.PENDING_EXIT
    assert ev_closed is None

    # Frame 3 outside -> exit confirmed
    ev_new, ev_closed = tracker.update(is_inside_raw=False, current_time=5.6, exit_debounce_frames=3)
    assert tracker.state == ZoneIntrusionState.OUTSIDE
    assert ev_closed is not None
    assert ev_closed.end_time == 5.6
    assert ev_closed.duration_seconds > 5.0


def test_helmet_compliance_tracker_debounce():
    tracker = HelmetComplianceTracker(track_id=1, debounce_frames=3)

    # Frame 1 & 2 unhelmeted -> debounce pending
    n1, c1 = tracker.update(has_helmet=False, current_time=1.0)
    assert n1 is None
    n2, c2 = tracker.update(has_helmet=False, current_time=1.1)
    assert n2 is None

    # Frame 3 unhelmeted -> triggers violation
    n3, c3 = tracker.update(has_helmet=False, current_time=1.2)
    assert n3 is not None
    assert n3.violation_type == ViolationType.NO_HELMET
    assert n3.severity == ViolationSeverity.WARNING

    # Person wears helmet again for 3 frames -> resolves violation
    tracker.update(has_helmet=True, current_time=1.3)
    tracker.update(has_helmet=True, current_time=1.4)
    _, closed = tracker.update(has_helmet=True, current_time=1.5)
    assert closed is not None
    assert closed.violation_type == ViolationType.NO_HELMET
    assert closed.end_time == 1.5


def test_worker_safety_monitor_multi_zone():
    monitor = WorkerSafetyMonitor(camera_id="cam_east", enter_debounce_frames=2, exit_debounce_frames=2)
    zone1 = DangerZone(name="ZoneA", polygon=[(0, 0), (200, 0), (200, 200), (0, 200)])
    zone2 = DangerZone(name="ZoneB", polygon=[(300, 0), (500, 0), (500, 200), (300, 200)])

    # Worker 1 at (100, 100) in ZoneA, Worker 2 at (400, 100) in ZoneB
    p1 = _make_tracked_person(track_id=1, cx=100.0, cy=100.0, has_helmet=True)
    p2 = _make_tracked_person(track_id=2, cx=400.0, cy=100.0, has_helmet=True)

    # Frame 1
    new_ev, closed_ev = monitor.process([p1, p2], [zone1, zone2], current_time=0.0)
    assert len(new_ev) == 0

    # Frame 2 -> both enter confirmed
    new_ev, closed_ev = monitor.process([p1, p2], [zone1, zone2], current_time=0.1)
    assert len(new_ev) == 2
    assert p1.is_in_danger_zone is True
    assert p1.danger_zone_name == "ZoneA"
    assert p2.is_in_danger_zone is True
    assert p2.danger_zone_name == "ZoneB"
