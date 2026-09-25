"""
Pure Python & NumPy Implementation of ByteTrack
Based on: https://github.com/ifzhang/ByteTrack (Tag: v0.3.2, Commit: 174a799)
Licensed under MIT License.
"""

from __future__ import annotations

import time
from enum import Enum
from typing import List, Tuple, Optional
import numpy as np
from scipy.optimize import linear_sum_assignment

from perception.schemas.detection import BoundingBox, TrackedPerson


class TrackState(int, Enum):
    New = 0
    Tracked = 1
    Lost = 2
    Removed = 3


class STrack:
    shared_id = 0

    def __init__(self, bbox: BoundingBox):
        # [x1, y1, x2, y2]
        self._tlbr = np.array([bbox.x1, bbox.y1, bbox.x2, bbox.y2], dtype=np.float32)
        self.score = bbox.conf
        self.class_id = bbox.class_id
        self.class_name = bbox.class_name

        self.track_id = 0
        self.is_activated = False
        self.state = TrackState.New

        self.start_frame = 0
        self.frame_id = 0
        self.time_since_update = 0

        # Monotonic time tracking
        self.start_time = time.monotonic()
        self.last_update_time = time.monotonic()
        self.in_danger_zone = False
        self.danger_zone_name: Optional[str] = None
        self.danger_zone_enter_time: Optional[float] = None
        self.dwell_time_seconds: float = 0.0

        # Helmet and head attributes
        self.has_helmet: bool = bool(getattr(bbox, "has_helmet", False))
        self.helmet_box: Optional[BoundingBox] = getattr(bbox, "helmet_box", None)
        self.head_box: Optional[BoundingBox] = getattr(bbox, "head_box", None)

        # Trajectory history of feet points (max 50 points)
        self.trajectory: List[Tuple[float, float]] = []

    @property
    def tlbr(self) -> np.ndarray:
        return self._tlbr

    @property
    def feet_point(self) -> Tuple[float, float]:
        x1, y1, x2, y2 = self._tlbr
        return (float(x1 + (x2 - x1) / 2.0), float(y2))

    @staticmethod
    def next_id() -> int:
        STrack.shared_id += 1
        return STrack.shared_id

    def activate(self, frame_id: int):
        self.track_id = self.next_id()
        self.state = TrackState.Tracked
        if frame_id == 1:
            self.is_activated = True
        self.frame_id = frame_id
        self.start_frame = frame_id
        self.start_time = time.monotonic()
        self.last_update_time = time.monotonic()
        self.trajectory.append(self.feet_point)

    def re_activate(self, new_track: STrack, frame_id: int, new_id: bool = False):
        self._tlbr = new_track._tlbr
        self.score = new_track.score
        self.state = TrackState.Tracked
        self.is_activated = True
        self.frame_id = frame_id
        if new_id:
            self.track_id = self.next_id()
        self.has_helmet = new_track.has_helmet
        self.helmet_box = new_track.helmet_box
        self.head_box = new_track.head_box
        self.time_since_update = 0
        self.last_update_time = time.monotonic()
        self.trajectory.append(self.feet_point)
        if len(self.trajectory) > 50:
            self.trajectory.pop(0)

    def update(self, new_track: STrack, frame_id: int):
        self.frame_id = frame_id
        self.time_since_update = 0
        self._tlbr = new_track._tlbr
        self.score = new_track.score
        self.state = TrackState.Tracked
        self.is_activated = True
        self.has_helmet = new_track.has_helmet
        self.helmet_box = new_track.helmet_box
        self.head_box = new_track.head_box
        self.last_update_time = time.monotonic()

        self.trajectory.append(self.feet_point)
        if len(self.trajectory) > 50:
            self.trajectory.pop(0)

    def mark_lost(self):
        self.state = TrackState.Lost

    def mark_removed(self):
        self.state = TrackState.Removed

    def to_schema(self, has_helmet: Optional[bool] = None) -> TrackedPerson:
        x1, y1, x2, y2 = self._tlbr
        bbox = BoundingBox(
            x1=float(x1),
            y1=float(y1),
            x2=float(x2),
            y2=float(y2),
            conf=float(self.score),
            class_id=self.class_id,
            class_name=self.class_name,
            has_helmet=self.has_helmet,
            helmet_box=self.helmet_box,
            head_box=self.head_box,
        )
        resolved_helmet = self.has_helmet if has_helmet is None else has_helmet
        return TrackedPerson(
            track_id=self.track_id,
            bbox=bbox,
            feet_point=self.feet_point,
            has_helmet=resolved_helmet,
            helmet_box=self.helmet_box,
            head_box=self.head_box,
            is_in_danger_zone=self.in_danger_zone,
            danger_zone_name=self.danger_zone_name,
            dwell_time_seconds=self.dwell_time_seconds,
            trajectory=list(self.trajectory),
        )


def calculate_ious(atlbrs: np.ndarray, btlbrs: np.ndarray) -> np.ndarray:
    """Calculates IoU matrix between tracks and detections."""
    if len(atlbrs) == 0 or len(btlbrs) == 0:
        return np.zeros((len(atlbrs), len(btlbrs)), dtype=np.float32)

    ious = np.zeros((len(atlbrs), len(btlbrs)), dtype=np.float32)
    for i, a in enumerate(atlbrs):
        a_area = (a[2] - a[0]) * (a[3] - a[1])
        for j, b in enumerate(btlbrs):
            b_area = (b[2] - b[0]) * (b[3] - b[1])
            iw = max(0.0, min(a[2], b[2]) - max(a[0], b[0]))
            ih = max(0.0, min(a[3], b[3]) - max(a[1], b[1]))
            inter = iw * ih
            union = a_area + b_area - inter
            if union > 0:
                ious[i, j] = inter / union
    return ious


class BYTETracker:
    """
    ByteTrack multi-object tracking manager.
    Associates high-confidence detections first, then low-confidence detections.
    """

    def __init__(
        self,
        track_thresh: float = 0.5,
        match_thresh: float = 0.7,
        max_lost_frames: int = 30,
    ):
        self.track_thresh = track_thresh
        self.match_thresh = match_thresh
        self.max_lost_frames = max_lost_frames

        self.tracked_stracks: List[STrack] = []
        self.lost_stracks: List[STrack] = []
        self.removed_stracks: List[STrack] = []

        self.frame_id = 0

    def reset(self):
        STrack.shared_id = 0
        self.tracked_stracks.clear()
        self.lost_stracks.clear()
        self.removed_stracks.clear()
        self.frame_id = 0

    def update(self, bboxes: List[BoundingBox]) -> List[TrackedPerson]:
        """
        Updates tracking state with detected bboxes from current frame.
        :param bboxes: list of BoundingBox objects for person detections
        :return: list of active TrackedPerson schemas
        """
        self.frame_id += 1
        activated_stracks: List[STrack] = []
        refind_stracks: List[STrack] = []
        lost_stracks: List[STrack] = []
        removed_stracks: List[STrack] = []

        # Split into high-conf and low-conf detections
        high_dets = [STrack(b) for b in bboxes if b.conf >= self.track_thresh]
        low_dets = [STrack(b) for b in bboxes if b.conf < self.track_thresh]

        # Active pool
        unconfirmed: List[STrack] = []
        tracked_pool: List[STrack] = []
        for track in self.tracked_stracks:
            if not track.is_activated:
                unconfirmed.append(track)
            else:
                tracked_pool.append(track)

        strack_pool = tracked_pool + self.lost_stracks

        # 1st association: High score detections with tracks
        dists = 1.0 - calculate_ious(
            np.array([t.tlbr for t in strack_pool]),
            np.array([d.tlbr for d in high_dets]),
        ) if len(strack_pool) and len(high_dets) else np.empty((len(strack_pool), len(high_dets)))

        matched_tracks, unmatched_tracks, unmatched_dets = self._linear_assignment(dists, self.match_thresh)

        for itracked, idet in matched_tracks:
            track = strack_pool[itracked]
            det = high_dets[idet]
            if track.state == TrackState.Tracked:
                track.update(det, self.frame_id)
                activated_stracks.append(track)
            else:
                track.re_activate(det, self.frame_id, new_id=False)
                refind_stracks.append(track)

        # 2nd association: Low score detections with remaining tracks
        r_tracked_stracks = [strack_pool[i] for i in unmatched_tracks if strack_pool[i].state == TrackState.Tracked]
        dists_low = 1.0 - calculate_ious(
            np.array([t.tlbr for t in r_tracked_stracks]),
            np.array([d.tlbr for d in low_dets]),
        ) if len(r_tracked_stracks) and len(low_dets) else np.empty((len(r_tracked_stracks), len(low_dets)))

        matched_low, unmatched_low_tracks, _ = self._linear_assignment(dists_low, 0.5)

        for itracked, idet in matched_low:
            track = r_tracked_stracks[itracked]
            det = low_dets[idet]
            track.update(det, self.frame_id)
            activated_stracks.append(track)

        for itracked in unmatched_low_tracks:
            track = r_tracked_stracks[itracked]
            if track.state != TrackState.Lost:
                track.mark_lost()
                lost_stracks.append(track)

        # Deal with unconfirmed tracks
        unmatched_high_dets = [high_dets[i] for i in unmatched_dets]
        dists_unconfirmed = 1.0 - calculate_ious(
            np.array([t.tlbr for t in unconfirmed]),
            np.array([d.tlbr for d in unmatched_high_dets]),
        ) if len(unconfirmed) and len(unmatched_high_dets) else np.empty((len(unconfirmed), len(unmatched_high_dets)))

        matched_unc, unmatched_unc_tracks, unmatched_new_dets = self._linear_assignment(dists_unconfirmed, 0.7)

        for itracked, idet in matched_unc:
            unconfirmed[itracked].update(unmatched_high_dets[idet], self.frame_id)
            activated_stracks.append(unconfirmed[itracked])

        for itracked in unmatched_unc_tracks:
            track = unconfirmed[itracked]
            track.mark_removed()
            removed_stracks.append(track)

        # Init new tracks
        for idet in unmatched_new_dets:
            track = unmatched_high_dets[idet]
            track.activate(self.frame_id)
            activated_stracks.append(track)

        # Remove dead tracks
        for track in self.lost_stracks:
            if self.frame_id - track.frame_id > self.max_lost_frames:
                track.mark_removed()
                removed_stracks.append(track)

        # Update track state lists
        self.tracked_stracks = [t for t in self.tracked_stracks if t.state == TrackState.Tracked]
        self.tracked_stracks.extend([t for t in activated_stracks if t not in self.tracked_stracks])
        self.tracked_stracks.extend(refind_stracks)
        self.lost_stracks = [t for t in self.lost_stracks if t.state == TrackState.Lost and t not in lost_stracks]
        self.lost_stracks.extend(lost_stracks)
        self.removed_stracks.extend(removed_stracks)

        # Filter and return active tracks
        output_stracks = [track for track in self.tracked_stracks if track.is_activated]
        return [track.to_schema() for track in output_stracks]

    @staticmethod
    def _linear_assignment(cost_matrix: np.ndarray, thresh: float):
        if cost_matrix.size == 0:
            return [], list(range(cost_matrix.shape[0])), list(range(cost_matrix.shape[1]))

        row_ind, col_ind = linear_sum_assignment(cost_matrix)
        matches = []
        unmatched_a = list(range(cost_matrix.shape[0]))
        unmatched_b = list(range(cost_matrix.shape[1]))

        for r, c in zip(row_ind, col_ind):
            if cost_matrix[r, c] <= thresh:
                matches.append((r, c))
                if r in unmatched_a:
                    unmatched_a.remove(r)
                if c in unmatched_b:
                    unmatched_b.remove(c)

        return matches, unmatched_a, unmatched_b
