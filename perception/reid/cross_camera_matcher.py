"""
Cross-Camera Person Matcher.

Maintains a time-decaying gallery of person embeddings per camera
and matches newly observed persons against other cameras' galleries
using cosine similarity (dot-product on L2-normalised vectors).
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

import numpy as np

logger = logging.getLogger("perception.reid")


@dataclass
class GalleryEntry:
    track_id: int
    camera_id: str
    global_id: str  # assigned cross-camera id
    embedding: np.ndarray
    last_seen: float  # monotonic timestamp
    frame_count: int = 1


class CrossCameraMatcher:
    """
    Matches persons across cameras using appearance embeddings.

    Supports up to `max_gallery_size` recent gallery entries;
    entries older than `gallery_ttl_seconds` are evicted.
    """

    def __init__(
        self,
        match_threshold: float = 0.65,
        gallery_ttl_seconds: float = 30.0,
        max_gallery_size: int = 200,
        min_frames_for_match: int = 5,
    ):
        self._match_threshold = match_threshold
        self._gallery_ttl = gallery_ttl_seconds
        self._max_gallery = max_gallery_size
        self._min_frames = min_frames_for_match

        self._gallery: list[GalleryEntry] = []
        self._global_id_counter = 0
        # Per-camera, per-track: most recent embedding for fast lookup
        self._track_index: dict[tuple[str, int], GalleryEntry] = {}

    def _next_global_id(self) -> str:
        self._global_id_counter += 1
        return f"G{self._global_id_counter:06d}"

    def register(
        self,
        track_id: int,
        camera_id: str,
        embedding: np.ndarray,
        current_time: Optional[float] = None,
    ) -> str:
        """
        Register or update a tracked person from a single camera frame.

        Returns the assigned global (cross-camera) identifier for this track.
        """
        now = current_time if current_time is not None else time.monotonic()
        key = (camera_id, track_id)

        # Update existing entry
        existing = self._track_index.get(key)
        if existing is not None:
            # Exponential moving average of embedding
            alpha = 0.3
            existing.embedding = alpha * embedding + (1 - alpha) * existing.embedding
            existing.embedding /= np.linalg.norm(existing.embedding) + 1e-8
            existing.last_seen = now
            existing.frame_count += 1
            return existing.global_id

        # New track: try to match against gallery from OTHER cameras
        matched_global_id = self._match_against_others(camera_id, embedding, now)

        if matched_global_id is None:
            matched_global_id = self._next_global_id()

        entry = GalleryEntry(
            track_id=track_id,
            camera_id=camera_id,
            global_id=matched_global_id,
            embedding=embedding.copy(),
            last_seen=now,
        )
        self._gallery.append(entry)
        self._track_index[key] = entry

        # Evict old entries
        self._evict(now)

        if matched_global_id and matched_global_id != self._track_index.get(key, entry).global_id:
            logger.debug("[ReID] Cross-camera match: %s:%d -> %s", camera_id, track_id, matched_global_id)
        return matched_global_id

    def _match_against_others(
        self, camera_id: str, embedding: np.ndarray, now: float
    ) -> Optional[str]:
        """Search other cameras' galleries for a matching person."""
        candidates = [
            e for e in self._gallery
            if e.camera_id != camera_id
            and (now - e.last_seen) < self._gallery_ttl
        ]
        if not candidates:
            return None

        candidate_embs = np.stack([e.embedding for e in candidates])
        # Cosine similarity via dot product (embeddings are L2-normalised)
        similarities = np.dot(candidate_embs, embedding)

        best_idx = int(np.argmax(similarities))
        best_score = float(similarities[best_idx])

        if best_score >= self._match_threshold:
            return candidates[best_idx].global_id
        return None

    def _evict(self, now: float) -> None:
        """Remove expired and excess gallery entries."""
        # Remove expired
        cutoff = now - self._gallery_ttl
        self._gallery = [e for e in self._gallery if e.last_seen >= cutoff]

        # Keep per-track mapping in sync
        active_keys = {(e.camera_id, e.track_id) for e in self._gallery}
        stale_keys = [k for k in self._track_index if k not in active_keys]
        for k in stale_keys:
            del self._track_index[k]

        # Trim to max size (FIFO)
        if len(self._gallery) > self._max_gallery:
            removed = self._gallery[:len(self._gallery) - self._max_gallery]
            self._gallery = self._gallery[len(self._gallery) - self._max_gallery:]
            for e in removed:
                self._track_index.pop((e.camera_id, e.track_id), None)

    def get_global_id(self, track_id: int, camera_id: str) -> Optional[str]:
        """Look up global ID for a currently tracked person."""
        entry = self._track_index.get((camera_id, track_id))
        return entry.global_id if entry else None

    def stats(self) -> dict:
        total = len(self._gallery)
        cameras = set(e.camera_id for e in self._gallery)
        global_ids = set(e.global_id for e in self._gallery)
        cross_matches = sum(1 for e in self._gallery if any(
            oe.global_id == e.global_id and oe.camera_id != e.camera_id
            for oe in self._gallery
        ))
        return {
            "gallery_size": total,
            "unique_cameras": len(cameras),
            "global_persons": len(global_ids),
            "cross_camera_matches": cross_matches,
        }