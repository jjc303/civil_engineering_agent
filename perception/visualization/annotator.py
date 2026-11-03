from __future__ import annotations

from typing import TYPE_CHECKING, Any, List, Optional, Sequence, Tuple
import cv2
import numpy as np

from perception.schemas.detection import (
    BoundingBox,
    DangerZone,
    ViolationEvent,
    ViolationSeverity,
    ViolationType,
)

if TYPE_CHECKING:
    from perception.tracking.safety_pipeline import PipelineFrameResult


def clamped_box(box: Any, width: int, height: int) -> tuple[int, int, int, int]:
    """Convert a model box to a drawable rectangle inside a frame."""
    x1 = max(0, min(width - 1, round(float(box.x1))))
    y1 = max(0, min(height - 1, round(float(box.y1))))
    x2 = max(x1 + 1, min(width - 1, round(float(box.x2))))
    y2 = max(y1 + 1, min(height - 1, round(float(box.y2))))
    return x1, y1, x2, y2


def draw_label(frame: np.ndarray, text: str, origin: tuple[int, int], color: tuple[int, int, int]) -> None:
    """Draw a high-contrast ASCII label while keeping it inside the preview frame."""
    font, scale, thickness = cv2.FONT_HERSHEY_SIMPLEX, 0.45, 1
    (text_width, text_height), baseline = cv2.getTextSize(text, font, scale, thickness)
    x = max(0, min(frame.shape[1] - text_width - 4, int(origin[0])))
    y = max(text_height + baseline + 4, min(frame.shape[0] - 3, int(origin[1])))
    cv2.rectangle(frame, (x, y - text_height - baseline - 3), (x + text_width + 4, y + 3), color, -1)
    cv2.putText(frame, text, (x + 2, y), font, scale, (255, 255, 255), thickness, cv2.LINE_AA)


class SnapshotAnnotator:
    """Renders annotated violation snapshot frames with zone overlays and top banner."""

    def __init__(
        self,
        zone_color: tuple[int, int, int] = (0, 0, 255),
        zone_alpha: float = 0.3,
        bbox_color: tuple[int, int, int] = (0, 0, 255),
        critical_banner_color: tuple[int, int, int] = (0, 0, 180),
        warning_banner_color: tuple[int, int, int] = (0, 140, 255),
        banner_height: int = 36,
    ) -> None:
        self.zone_color = zone_color
        self.zone_alpha = zone_alpha
        self.bbox_color = bbox_color
        self.critical_banner_color = critical_banner_color
        self.warning_banner_color = warning_banner_color
        self.banner_height = banner_height

    def annotate(
        self,
        frame: np.ndarray,
        event: ViolationEvent,
        person_bbox: Optional[BoundingBox] = None,
        zone_polygon: Optional[List[Tuple[float, float]]] = None,
    ) -> np.ndarray:
        annotated = frame.copy()
        _, w = annotated.shape[:2]

        if zone_polygon and len(zone_polygon) >= 3:
            pts = np.array(zone_polygon, dtype=np.int32).reshape((-1, 1, 2))
            overlay = annotated.copy()
            cv2.fillPoly(overlay, [pts], self.zone_color)
            cv2.addWeighted(overlay, self.zone_alpha, annotated, 1.0 - self.zone_alpha, 0, annotated)
            cv2.polylines(annotated, [pts], isClosed=True, color=self.zone_color, thickness=2)

        if person_bbox is not None:
            bx1, by1 = int(person_bbox.x1), int(person_bbox.y1)
            bx2, by2 = int(person_bbox.x2), int(person_bbox.y2)
            cv2.rectangle(annotated, (bx1, by1), (bx2, by2), self.bbox_color, 2)
            label = f"ID:{event.track_id} {event.violation_type}"
            cv2.putText(
                annotated,
                label,
                (bx1, max(15, by1 - 5)),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                self.bbox_color,
                2,
            )

        banner = np.zeros((self.banner_height, w, 3), dtype=np.uint8)
        banner_color = (
            self.critical_banner_color
            if event.severity == ViolationSeverity.CRITICAL
            else self.warning_banner_color
        )
        banner[:] = banner_color
        banner_text = (
            f"[{event.severity}] {event.violation_type} | Cam: {event.camera_id} | "
            f"Track: {event.track_id} | Zone: {event.zone_name or 'N/A'}"
        )
        cv2.putText(banner, banner_text, (10, 24), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 255, 255), 2)

        return np.vstack([banner, annotated])


def render_preview_frame(
    frame: np.ndarray,
    result: "PipelineFrameResult",
    zones: Sequence[DangerZone],
) -> np.ndarray:
    """Draw live safety context without modifying the frame used by the pipeline."""
    preview = frame.copy()
    if preview.ndim == 2:
        preview = cv2.cvtColor(preview, cv2.COLOR_GRAY2BGR)

    people = list(getattr(result, "tracked_persons", []))
    active_violations = list(getattr(result, "active_violations", []))

    zone_overlay = preview.copy()
    for index, zone in enumerate(zones, start=1):
        if len(zone.polygon) < 3:
            continue
        points = np.asarray(zone.polygon, dtype=np.int32).reshape((-1, 1, 2))
        occupied = any(person.is_in_danger_zone and person.danger_zone_name == zone.name for person in people)
        color = (0, 0, 255) if occupied else (0, 180, 255)
        cv2.fillPoly(zone_overlay, [points], color)
        cv2.polylines(preview, [points], True, color, 2, cv2.LINE_AA)
        draw_label(preview, f"DANGER ZONE {index}", tuple(points[0, 0]), color)
    if zones:
        cv2.addWeighted(zone_overlay, 0.16, preview, 0.84, 0, preview)

    intrusion_count = dwell_alert_count = 0
    for person in people:
        x1, y1, x2, y2 = clamped_box(person.bbox, preview.shape[1], preview.shape[0])
        is_intrusion = bool(person.is_in_danger_zone)
        is_dwell_alert = any(
            violation.track_id == person.track_id
            and violation.violation_type == ViolationType.DANGER_ZONE_INTRUSION
            and violation.severity == ViolationSeverity.CRITICAL
            and violation.status == "ACTIVE"
            for violation in active_violations
        )
        if is_dwell_alert:
            color = (0, 0, 255)
            dwell_alert_count += 1
        elif is_intrusion or not person.has_helmet:
            color = (0, 165, 255)
        else:
            color = (0, 200, 0)
        cv2.rectangle(preview, (x1, y1), (x2, y2), color, 2, cv2.LINE_AA)

        if person.helmet_box is not None:
            hx1, hy1, hx2, hy2 = clamped_box(person.helmet_box, preview.shape[1], preview.shape[0])
            cv2.rectangle(preview, (hx1, hy1), (hx2, hy2), (255, 220, 0), 2, cv2.LINE_AA)
        elif person.head_box is not None:
            hx1, hy1, hx2, hy2 = clamped_box(person.head_box, preview.shape[1], preview.shape[0])
            cv2.rectangle(preview, (hx1, hy1), (hx2, hy2), (0, 0, 255), 2, cv2.LINE_AA)

        helmet_text = "HELMET" if person.has_helmet else "NO HELMET"
        label = f"ID {person.track_id}"
        if getattr(person, "global_id", None):
            label += f" | {person.global_id}"
        label += f" | {helmet_text}"
        if is_intrusion:
            intrusion_count += 1
            label += " | INTRUSION"
        if is_dwell_alert:
            label += f" | DWELL {person.dwell_time_seconds:.1f}s"
        draw_label(preview, label, (x1, y1 - 6), color)

    active_no_helmet = sum(
        violation.violation_type == ViolationType.NO_HELMET and violation.status == "ACTIVE"
        for violation in active_violations
    )
    if active_no_helmet or intrusion_count or dwell_alert_count:
        banner = f"ACTIVE ALERTS  NO HELMET:{active_no_helmet}  INTRUSION:{intrusion_count}  CRITICAL:{dwell_alert_count}"
        cv2.rectangle(preview, (0, 0), (min(preview.shape[1], max(440, len(banner) * 9)), 30), (0, 0, 180), -1)
        cv2.putText(preview, banner, (8, 21), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1, cv2.LINE_AA)
    return preview
