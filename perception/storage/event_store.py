from __future__ import annotations

import datetime
import json
from pathlib import Path
import sqlite3
from typing import Any, Dict, List, Optional, Tuple, Union
import cv2
import numpy as np

from perception.config import DEFAULT_EVENT_DB, DEFAULT_SNAPSHOT_DIR
from perception.schemas.detection import (
    BoundingBox,
    ViolationEvent,
    ViolationSeverity,
    ViolationType,
)
from perception.visualization.annotator import SnapshotAnnotator


class EventStore:
    """
    Manages SQLite persistence for safety violation events and snapshot image archiving.
    """

    def __init__(
        self,
        db_path: Union[str, Path] = DEFAULT_EVENT_DB,
        snapshot_dir: Optional[Union[str, Path]] = DEFAULT_SNAPSHOT_DIR,
        annotator: Optional[SnapshotAnnotator] = None,
    ):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        if snapshot_dir is None:
            self.snapshot_dir = self.db_path.parent / "snapshots"
        else:
            self.snapshot_dir = Path(snapshot_dir)
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self.annotator = annotator or SnapshotAnnotator()

        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path), timeout=10.0)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS violation_events (
                    event_uuid TEXT PRIMARY KEY,
                    track_id INTEGER NOT NULL,
                    camera_id TEXT NOT NULL,
                    violation_type TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    zone_name TEXT,
                    start_time REAL NOT NULL,
                    end_time REAL,
                    duration_seconds REAL NOT NULL DEFAULT 0.0,
                    snapshot_path TEXT,
                    extra_details TEXT,
                    created_at TEXT NOT NULL
                )
            """)
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_track ON violation_events(track_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_type ON violation_events(violation_type)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_time ON violation_events(start_time)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_events_camera ON violation_events(camera_id)")
            conn.commit()

    def save_event(
        self,
        event: ViolationEvent,
        frame: Optional[np.ndarray] = None,
        person_bbox: Optional[BoundingBox] = None,
        zone_polygon: Optional[List[Tuple[float, float]]] = None,
        extra_details: Optional[Dict[str, Any]] = None,
    ) -> ViolationEvent:
        """
        Saves a ViolationEvent to SQLite. If frame is provided, renders and archives an annotated snapshot.
        """
        snapshot_rel_path: Optional[str] = event.snapshot_path

        if frame is not None and snapshot_rel_path is None:
            snapshot_rel_path = self._archive_snapshot(
                event=event,
                frame=frame,
                person_bbox=person_bbox,
                zone_polygon=zone_polygon,
            )
            event.snapshot_path = snapshot_rel_path

        created_at_iso = event.created_at or datetime.datetime.now(datetime.timezone.utc).isoformat()
        event.created_at = created_at_iso
        extra_json = json.dumps(extra_details or {}, ensure_ascii=False)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO violation_events (
                    event_uuid, track_id, camera_id, violation_type,
                    severity, zone_name, start_time, end_time,
                    duration_seconds, snapshot_path, extra_details, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                event.event_uuid,
                event.track_id,
                event.camera_id,
                event.violation_type.value if hasattr(event.violation_type, "value") else str(event.violation_type),
                event.severity.value if hasattr(event.severity, "value") else str(event.severity),
                event.zone_name,
                float(event.start_time),
                float(event.end_time) if event.end_time is not None else None,
                float(event.duration_seconds),
                snapshot_rel_path,
                extra_json,
                created_at_iso,
            ))
            conn.commit()

        return event

    def _archive_snapshot(
        self,
        event: ViolationEvent,
        frame: np.ndarray,
        person_bbox: Optional[BoundingBox] = None,
        zone_polygon: Optional[List[Tuple[float, float]]] = None,
    ) -> str:
        """
        Annotates frame with danger polygon, person bounding box, and warning overlay,
        then saves JPEG to snapshot directory.
        :return: relative snapshot path
        """
        final_img = self.annotator.annotate(
            frame=frame,
            event=event,
            person_bbox=person_bbox,
            zone_polygon=zone_polygon,
        )

        # Subdirectory by date: YYYYMMDD
        date_str = datetime.date.today().strftime("%Y%m%d")
        sub_dir = self.snapshot_dir / date_str
        sub_dir.mkdir(parents=True, exist_ok=True)

        # Ensure compatibility if snapshot_dir is named 'snapshots'
        if self.snapshot_dir.name == "snapshots":
            symlink_alias = self.snapshot_dir / "snapshots"
            if not symlink_alias.exists():
                try:
                    symlink_alias.symlink_to(".", target_is_directory=True)
                except OSError:
                    pass

        filename = f"{event.event_uuid}.jpg"
        file_path = sub_dir / filename
        cv2.imwrite(str(file_path), final_img, [cv2.IMWRITE_JPEG_QUALITY, 85])

        # Return standardized relative media URI: snapshots/YYYYMMDD/{uuid}.jpg
        return f"snapshots/{date_str}/{filename}"

    def get_snapshot_full_path(self, snapshot_path: str) -> Path:
        """
        Resolves a relative snapshot URI (e.g. snapshots/20260925/uuid.jpg or 20260925/uuid.jpg)
        to the full Path on disk.
        """
        p = Path(snapshot_path)
        if p.parts and p.parts[0] == "snapshots":
            rel_p = Path(*p.parts[1:])
        else:
            rel_p = p

        candidate = self.snapshot_dir / rel_p
        if candidate.exists():
            return candidate
        return self.snapshot_dir / snapshot_path

    def close_event(
        self,
        event_uuid: str,
        end_time: float,
        duration_seconds: Optional[float] = None,
    ) -> bool:
        """
        Marks an event as closed/resolved with end timestamp.
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if duration_seconds is not None:
                cursor.execute("""
                    UPDATE violation_events
                    SET end_time = ?, duration_seconds = ?
                    WHERE event_uuid = ?
                """, (float(end_time), float(duration_seconds), event_uuid))
            else:
                cursor.execute("""
                    UPDATE violation_events
                    SET end_time = ?, duration_seconds = MAX(0.0, ? - start_time)
                    WHERE event_uuid = ?
                """, (float(end_time), float(end_time), event_uuid))
            conn.commit()
            return cursor.rowcount > 0

    def get_event_by_id(self, event_uuid: str) -> Optional[ViolationEvent]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM violation_events WHERE event_uuid = ?", (event_uuid,))
            row = cursor.fetchone()
            if row is None:
                return None
            return self._row_to_event(row)

    def query_events(
        self,
        camera_id: Optional[str] = None,
        violation_type: Optional[Union[ViolationType, str]] = None,
        severity: Optional[Union[ViolationSeverity, str]] = None,
        start_time_ge: Optional[float] = None,
        end_time_le: Optional[float] = None,
        limit: int = 100,
    ) -> List[ViolationEvent]:
        query = "SELECT * FROM violation_events WHERE 1=1"
        params: List[Any] = []

        if camera_id:
            query += " AND camera_id = ?"
            params.append(camera_id)
        if violation_type:
            val = violation_type.value if hasattr(violation_type, "value") else str(violation_type)
            query += " AND violation_type = ?"
            params.append(val)
        if severity:
            val = severity.value if hasattr(severity, "value") else str(severity)
            query += " AND severity = ?"
            params.append(val)
        if start_time_ge is not None:
            query += " AND start_time >= ?"
            params.append(float(start_time_ge))
        if end_time_le is not None:
            query += " AND start_time <= ?"
            params.append(float(end_time_le))

        query += " ORDER BY start_time DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(query, params)
            rows = cursor.fetchall()
            return [self._row_to_event(r) for r in rows]

    def get_statistics(
        self,
        start_time_ge: Optional[float] = None,
        end_time_le: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Calculates aggregate violation statistics.
        """
        where_clauses = ["1=1"]
        params: List[Any] = []

        if start_time_ge is not None:
            where_clauses.append("start_time >= ?")
            params.append(float(start_time_ge))
        if end_time_le is not None:
            where_clauses.append("start_time <= ?")
            params.append(float(end_time_le))

        where_sql = " AND ".join(where_clauses)

        with self._get_connection() as conn:
            cursor = conn.cursor()

            # Total events and avg duration
            cursor.execute(
                f"SELECT COUNT(*), AVG(duration_seconds) FROM violation_events WHERE {where_sql}",
                params,
            )
            total_count, avg_duration = cursor.fetchone()
            total_count = total_count or 0
            avg_duration = round(float(avg_duration or 0.0), 2)

            # By violation type
            cursor.execute(
                f"SELECT violation_type, COUNT(*) FROM violation_events WHERE {where_sql} GROUP BY violation_type",
                params,
            )
            by_type = dict(cursor.fetchall())

            # By severity
            cursor.execute(
                f"SELECT severity, COUNT(*) FROM violation_events WHERE {where_sql} GROUP BY severity",
                params,
            )
            by_severity = dict(cursor.fetchall())

            return {
                "total_violations": total_count,
                "average_duration_seconds": avg_duration,
                "by_type": by_type,
                "by_severity": by_severity,
            }

    def aggregate_by_date(self, date_str: str) -> Dict[str, Any]:
        """
        Aggregates SQLite violation events by date using SQL filtering and grouping.
        Accepts formats: 'YYYYMMDD' or 'YYYY-MM-DD'.
        """
        clean_date = date_str.replace("-", "")
        formatted_iso_date = (
            f"{clean_date[:4]}-{clean_date[4:6]}-{clean_date[6:8]}"
            if len(clean_date) == 8
            else date_str
        )
        where_sql = (
            "(substr(created_at, 1, 10) = ? "
            "OR instr(created_at, ?) > 0 "
            "OR instr(COALESCE(snapshot_path, ''), ?) > 0)"
        )
        params = (formatted_iso_date, clean_date, f"snapshots/{clean_date}/")

        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                f"SELECT violation_type, COUNT(*) FROM violation_events WHERE {where_sql} GROUP BY violation_type",
                params,
            )
            by_type = dict(cursor.fetchall())

            cursor.execute(
                f"SELECT severity, COUNT(*) FROM violation_events WHERE {where_sql} GROUP BY severity",
                params,
            )
            by_severity = dict(cursor.fetchall())

            cursor.execute(
                f"SELECT camera_id, COUNT(*) FROM violation_events WHERE {where_sql} GROUP BY camera_id",
                params,
            )
            by_camera = dict(cursor.fetchall())

            cursor.execute(
                f"SELECT * FROM violation_events WHERE {where_sql} ORDER BY start_time DESC",
                params,
            )
            date_events = [self._row_to_event(r) for r in cursor.fetchall()]

        resolved_count = sum(1 for ev in date_events if ev.status == "RESOLVED" or ev.end_time is not None)
        active_count = len(date_events) - resolved_count

        return {
            "date": formatted_iso_date,
            "total_violations": len(date_events),
            "by_type": by_type,
            "by_severity": by_severity,
            "by_camera": by_camera,
            "resolved_count": resolved_count,
            "active_count": active_count,
            "events": [
                {
                    "event_uuid": ev.event_uuid,
                    "camera_id": ev.camera_id,
                    "track_id": ev.track_id,
                    "violation_type": ev.violation_type.value if hasattr(ev.violation_type, "value") else str(ev.violation_type),
                    "severity": ev.severity.value if hasattr(ev.severity, "value") else str(ev.severity),
                    "status": ev.status,
                    "zone_name": ev.zone_name,
                    "start_time": ev.start_time,
                    "duration_seconds": ev.duration_seconds,
                    "snapshot_uri": ev.snapshot_path,
                }
                for ev in date_events
            ],
        }

    @staticmethod
    def _row_to_event(row: sqlite3.Row) -> ViolationEvent:
        row_keys = row.keys()
        extra_dict = {}
        if "extra_details" in row_keys and row["extra_details"]:
            try:
                extra_dict = json.loads(row["extra_details"])
            except Exception:
                extra_dict = {}

        return ViolationEvent(
            event_uuid=row["event_uuid"],
            track_id=row["track_id"],
            camera_id=row["camera_id"],
            violation_type=ViolationType(row["violation_type"]),
            severity=ViolationSeverity(row["severity"]),
            zone_name=row["zone_name"],
            start_time=float(row["start_time"]),
            end_time=float(row["end_time"]) if row["end_time"] is not None else None,
            duration_seconds=float(row["duration_seconds"]),
            snapshot_path=row["snapshot_path"],
            created_at=row["created_at"] if "created_at" in row_keys else None,
            extra_details=extra_dict,
        )
