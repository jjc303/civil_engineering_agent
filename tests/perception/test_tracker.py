import pytest
from perception.schemas.detection import BoundingBox
from perception.tracking.byte_tracker import BYTETracker


def test_byte_tracker_association():
    tracker = BYTETracker(track_thresh=0.5, match_thresh=0.7, max_lost_frames=5)
    tracker.reset()

    # Frame 1: Person at (100, 100, 200, 300)
    det1 = [
        BoundingBox(
            x1=100.0,
            y1=100.0,
            x2=200.0,
            y2=300.0,
            conf=0.9,
            class_id=0,
            class_name="person",
        )
    ]
    tracks_frame1 = tracker.update(det1)
    assert len(tracks_frame1) == 1
    track_id = tracks_frame1[0].track_id
    assert track_id > 0

    # Frame 2: Person slightly moves to (105, 102, 205, 302)
    det2 = [
        BoundingBox(
            x1=105.0,
            y1=102.0,
            x2=205.0,
            y2=302.0,
            conf=0.88,
            class_id=0,
            class_name="person",
        )
    ]
    tracks_frame2 = tracker.update(det2)
    assert len(tracks_frame2) == 1
    # Track ID MUST be preserved (no ID switch)
    assert tracks_frame2[0].track_id == track_id

    # Frame 3: Missing detection (person occluded for 1 frame)
    tracks_frame3 = tracker.update([])
    assert len(tracks_frame3) == 0  # In lost state, not returned in active list

    # Frame 4: Person reappears at (110, 105, 210, 305)
    det4 = [
        BoundingBox(
            x1=110.0,
            y1=105.0,
            x2=210.0,
            y2=305.0,
            conf=0.85,
            class_id=0,
            class_name="person",
        )
    ]
    tracks_frame4 = tracker.update(det4)
    assert len(tracks_frame4) == 1
    # Successfully re-identified and recovered same track_id
    assert tracks_frame4[0].track_id == track_id


def test_byte_tracker_multi_instance_isolation():
    """Verify that multiple BYTETracker instances don't share IDs or conflict."""
    tracker_a = BYTETracker()
    tracker_b = BYTETracker()

    det_a = [
        BoundingBox(x1=50.0, y1=50.0, x2=100.0, y2=150.0, conf=0.9, class_id=0, class_name="person")
    ]
    det_b = [
        BoundingBox(x1=200.0, y1=200.0, x2=300.0, y2=400.0, conf=0.9, class_id=0, class_name="person")
    ]

    tracks_a = tracker_a.update(det_a)
    tracks_b = tracker_b.update(det_b)

    # Both start their own sequence from 1
    assert tracks_a[0].track_id == 1
    assert tracks_b[0].track_id == 1

    tracker_a.reset()
    assert tracker_a._next_id == 0
    # tracker_b is unaffected and assigns ID 2
    det_b2 = [
        BoundingBox(x1=10.0, y1=10.0, x2=20.0, y2=30.0, conf=0.9, class_id=0, class_name="person")
    ]
    tracker_b.update(det_b2)
    assert any(t.track_id == 2 for t in tracker_b.tracked_stracks)

    # Frame 3 confirms the new track
    tracks_b3 = tracker_b.update(det_b2)
    assert any(t.track_id == 2 for t in tracks_b3)

