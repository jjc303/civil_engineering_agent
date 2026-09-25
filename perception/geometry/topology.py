from __future__ import annotations

from enum import Enum
from typing import Iterable, List, Optional, Tuple, Union
import numpy as np
from pydantic import BaseModel, Field
from scipy.optimize import linear_sum_assignment

from perception.schemas.detection import BoundingBox


DEFAULT_PERSON_CLASSES: Tuple[Union[str, int], ...] = ("person", "worker", "pedestrian", 0)
DEFAULT_HELMET_CLASSES: Tuple[Union[str, int], ...] = ("helmet", "hard_hat", "hard-hat", "hardhat", 2)
DEFAULT_HEAD_CLASSES: Tuple[Union[str, int], ...] = ("head", "face", 1)


def _is_class_match(box: BoundingBox, allowed_classes: Iterable[Union[str, int]]) -> bool:
    name_lower = box.class_name.lower().strip()
    for target in allowed_classes:
        if isinstance(target, int):
            if box.class_id == target:
                return True
        elif isinstance(target, str):
            target_lower = target.lower().strip()
            if target_lower == name_lower or target_lower in name_lower:
                return True
    return False


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
    person_classes: Optional[Iterable[Union[str, int]]] = None,
    helmet_classes: Optional[Iterable[Union[str, int]]] = None,
    head_classes: Optional[Iterable[Union[str, int]]] = None,
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
    :param person_classes: optional custom class names/IDs for persons (defaults to DEFAULT_PERSON_CLASSES)
    :param helmet_classes: optional custom class names/IDs for helmets (defaults to DEFAULT_HELMET_CLASSES)
    :param head_classes: optional custom class names/IDs for bare heads (defaults to DEFAULT_HEAD_CLASSES)
    :return: list of PersonTopologyResult with compliance state and attached boxes
    """
    p_classes = person_classes if person_classes is not None else DEFAULT_PERSON_CLASSES
    h_classes = helmet_classes if helmet_classes is not None else DEFAULT_HELMET_CLASSES
    hd_classes = head_classes if head_classes is not None else DEFAULT_HEAD_CLASSES

    persons: List[BoundingBox] = []
    helmets: List[BoundingBox] = []
    heads: List[BoundingBox] = []

    for b in detections:
        if _is_class_match(b, p_classes):
            persons.append(b)
        elif _is_class_match(b, h_classes):
            helmets.append(b)
        elif _is_class_match(b, hd_classes):
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
