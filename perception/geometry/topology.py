from __future__ import annotations

from enum import Enum
from typing import List, Optional, Tuple
import numpy as np
from pydantic import BaseModel, Field
from scipy.optimize import linear_sum_assignment

from perception.schemas.detection import BoundingBox


class HelmetCompliance(str, Enum):
    HELMETED = "HELMETED"
    UNHELMETED = "UNHELMETED"
    UNKNOWN = "UNKNOWN"


class PersonTopologyResult(BaseModel):
    person_box: BoundingBox
    compliance: HelmetCompliance
    has_helmet: bool
    helmet_box: Optional[BoundingBox] = None
    head_box: Optional[BoundingBox] = None
    confidence: float = Field(1.0, ge=0.0, le=1.0)


def _compute_overlap_ratio(cand: BoundingBox, region: Tuple[float, float, float, float]) -> float:
    """
    Computes ratio of candidate box area that falls within the specified target region.
    region = (rx1, ry1, rx2, ry2)
    """
    rx1, ry1, rx2, ry2 = region
    ix1 = max(cand.x1, rx1)
    iy1 = max(cand.y1, ry1)
    ix2 = min(cand.x2, rx2)
    iy2 = min(cand.y2, ry2)

    iw = max(0.0, ix2 - ix1)
    ih = max(0.0, iy2 - iy1)
    inter_area = iw * ih

    cand_area = cand.width * cand.height
    if cand_area <= 0:
        return 0.0

    return inter_area / cand_area


def match_person_head_helmet(
    detections: List[BoundingBox],
    head_ratio: float = 0.35,
    min_containment_ratio: float = 0.4,
) -> List[PersonTopologyResult]:
    """
    Performs spatial topology matching between persons and detected helmets / bare heads.

    For each person bounding box, defines the anatomical upper head region:
      [x1 - 0.15*w, y1 - 0.2*h, x2 + 0.15*w, y1 + head_ratio*h]
    Matches candidate helmets and heads to the closest, most overlapping person using
    global bipartite matching (Hungarian algorithm) to avoid duplicate assignments.

    :param detections: list of all BoundingBoxes in current frame
    :param head_ratio: vertical fraction of person height representing head region (default 0.35)
    :param min_containment_ratio: minimum fraction of candidate helmet/head area inside person head region
    :return: list of PersonTopologyResult with compliance state and attached boxes
    """
    persons: List[BoundingBox] = []
    helmets: List[BoundingBox] = []
    heads: List[BoundingBox] = []

    for b in detections:
        name_lower = b.class_name.lower()
        if "person" in name_lower or b.class_id == 0:
            persons.append(b)
        elif "helmet" in name_lower or b.class_id == 2:
            helmets.append(b)
        elif "head" in name_lower or b.class_id == 1:
            heads.append(b)

    if not persons:
        return []

    # If neither helmet nor head was detected in frame, return all persons as UNKNOWN
    if not helmets and not heads:
        return [
            PersonTopologyResult(
                person_box=p,
                compliance=HelmetCompliance.UNKNOWN,
                has_helmet=False,
                confidence=p.conf,
            )
            for p in persons
        ]

    # Precalculate head regions for all persons
    person_head_regions: List[Tuple[float, float, float, float]] = []
    for p in persons:
        pw = p.width
        ph = p.height
        rx1 = p.x1 - 0.15 * pw
        ry1 = p.y1 - 0.20 * ph
        rx2 = p.x2 + 0.15 * pw
        ry2 = p.y1 + head_ratio * ph
        person_head_regions.append((rx1, ry1, rx2, ry2))

    # Match helmets to persons
    person_matched_helmet: List[Optional[BoundingBox]] = [None] * len(persons)
    if helmets:
        cost_matrix = np.full((len(persons), len(helmets)), 10.0, dtype=np.float32)
        for i, reg in enumerate(person_head_regions):
            for j, helmet in enumerate(helmets):
                ratio = _compute_overlap_ratio(helmet, reg)
                # Check horizontal center alignment
                p = persons[i]
                p_cx = p.center[0]
                h_cx = helmet.center[0]
                center_dist_x = abs(h_cx - p_cx) / max(1.0, p.width)
                if ratio >= min_containment_ratio and center_dist_x <= 0.5:
                    # Higher ratio & confidence gives lower cost
                    cost_matrix[i, j] = 1.0 - (0.7 * ratio + 0.3 * helmet.conf)

        row_ind, col_ind = linear_sum_assignment(cost_matrix)
        for r, c in zip(row_ind, col_ind):
            if cost_matrix[r, c] < 1.0:
                person_matched_helmet[r] = helmets[c]

    # Match heads to persons
    person_matched_head: List[Optional[BoundingBox]] = [None] * len(persons)
    if heads:
        cost_matrix_head = np.full((len(persons), len(heads)), 10.0, dtype=np.float32)
        for i, reg in enumerate(person_head_regions):
            for j, head in enumerate(heads):
                ratio = _compute_overlap_ratio(head, reg)
                p = persons[i]
                p_cx = p.center[0]
                h_cx = head.center[0]
                center_dist_x = abs(h_cx - p_cx) / max(1.0, p.width)
                if ratio >= min_containment_ratio and center_dist_x <= 0.5:
                    cost_matrix_head[i, j] = 1.0 - (0.7 * ratio + 0.3 * head.conf)

        row_ind, col_ind = linear_sum_assignment(cost_matrix_head)
        for r, c in zip(row_ind, col_ind):
            if cost_matrix_head[r, c] < 1.0:
                person_matched_head[r] = heads[c]

    # Build final results
    results: List[PersonTopologyResult] = []
    for i, p in enumerate(persons):
        matched_helmet = person_matched_helmet[i]
        matched_head = person_matched_head[i]

        if matched_helmet is not None:
            # Person has verified helmet
            compliance = HelmetCompliance.HELMETED
            has_helmet = True
            conf = matched_helmet.conf
        elif matched_head is not None:
            # Person has bare head detected, no helmet
            compliance = HelmetCompliance.UNHELMETED
            has_helmet = False
            conf = matched_head.conf
        else:
            # Neither detected on upper body
            compliance = HelmetCompliance.UNKNOWN
            has_helmet = False
            conf = p.conf

        results.append(
            PersonTopologyResult(
                person_box=p,
                compliance=compliance,
                has_helmet=has_helmet,
                helmet_box=matched_helmet,
                head_box=matched_head,
                confidence=conf,
            )
        )

    return results
