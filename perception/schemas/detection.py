from __future__ import annotations

import time
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from pydantic import BaseModel, Field


class ViolationType(str, Enum):
    NO_HELMET = "NO_HELMET"
    DANGER_ZONE_INTRUSION = "DANGER_ZONE_INTRUSION"
    DWELL_TIMEOUT = "DWELL_TIMEOUT"


class ViolationSeverity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class BoundingBox(BaseModel):
    x1: float = Field(..., description="Top-left X coordinate")
    y1: float = Field(..., description="Top-left Y coordinate")
    x2: float = Field(..., description="Bottom-right X coordinate")
    y2: float = Field(..., description="Bottom-right Y coordinate")
    conf: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    class_id: int = Field(..., description="Class ID (0: person, 1: head, 2: helmet)")
    class_name: str = Field(..., description="Class name ('person', 'head', 'helmet')")
    has_helmet: Optional[bool] = Field(None, description="Whether associated person wears safety helmet")
    helmet_box: Optional[BoundingBox] = Field(None, description="Associated helmet bounding box")
    head_box: Optional[BoundingBox] = Field(None, description="Associated bare head bounding box")

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def center(self) -> Tuple[float, float]:
        return (self.x1 + self.width / 2.0, self.y1 + self.height / 2.0)

    @property
    def feet_point(self) -> Tuple[float, float]:
        """Calculates bottom-center contact point on ground."""
        return (self.x1 + self.width / 2.0, self.y2)


class DetectionResult(BaseModel):
    frame_id: int = Field(0, description="Sequential frame index")
    timestamp: float = Field(default_factory=time.monotonic, description="Monotonic timestamp in seconds")
    boxes: List[BoundingBox] = Field(default_factory=list, description="Detected bounding boxes")
    inference_time_ms: float = Field(0.0, description="Time spent on inference in ms")


class TrackedPerson(BaseModel):
    track_id: int = Field(..., description="Global unique tracking ID")
    bbox: BoundingBox = Field(..., description="Current person bounding box")
    feet_point: Tuple[float, float] = Field(..., description="Calculated feet ground point")
    has_helmet: bool = Field(False, description="Whether person wears safety helmet")
    helmet_box: Optional[BoundingBox] = Field(None, description="Associated helmet bounding box")
    head_box: Optional[BoundingBox] = Field(None, description="Associated bare head bounding box")
    is_in_danger_zone: bool = Field(False, description="Whether person has entered a danger zone")
    danger_zone_name: Optional[str] = Field(None, description="Name of the invaded danger zone")
    dwell_time_seconds: float = Field(0.0, description="Continuous dwell duration in danger zone")
    trajectory: List[Tuple[float, float]] = Field(default_factory=list, description="Recent feet trajectory points")



class DangerZone(BaseModel):
    name: str = Field(..., description="Zone identifier, e.g., 'Crane_Area_1'")
    polygon: List[Tuple[float, float]] = Field(..., min_length=3, description="List of (x, y) vertices")
    alarm_dwell_threshold_seconds: float = Field(5.0, description="Threshold in seconds for critical alarm")
    enabled: bool = Field(True, description="Whether this zone is actively monitored")


class ViolationEvent(BaseModel):
    event_uuid: str = Field(..., description="Unique event UUID")
    track_id: int = Field(..., description="Associated person tracking ID")
    camera_id: str = Field(..., description="Camera ID or video source identifier")
    violation_type: ViolationType = Field(..., description="Type of safety violation")
    severity: ViolationSeverity = Field(ViolationSeverity.WARNING, description="Alert level")
    zone_name: Optional[str] = Field(None, description="Name of danger zone if applicable")
    start_time: float = Field(default_factory=time.monotonic, description="Timestamp when violation started")
    end_time: Optional[float] = Field(None, description="Timestamp when violation was resolved")
    duration_seconds: float = Field(0.0, description="Total violation duration")
    snapshot_path: Optional[str] = Field(None, description="Saved violation image snapshot path")
    status: str = Field("ACTIVE", description="Violation status: ACTIVE, RESOLVED, or FALSE_ALARM")
    monitor_session_id: Optional[str] = Field(None, description="Identifier of the monitoring session")
    created_at: Optional[str] = Field(None, description="ISO timestamp when violation was created/stored")
    extra_details: Dict[str, Any] = Field(default_factory=dict, description="Arbitrary metadata dictionary")


class CameraStatus(BaseModel):
    camera_id: str = Field(..., description="Camera identifier")
    is_online: bool = Field(True, description="Stream connectivity status")
    fps: float = Field(0.0, description="Current processing FPS")
    active_workers_count: int = Field(0, description="Number of tracked workers currently on site")
    helmet_compliance_rate: float = Field(1.0, ge=0.0, le=1.0, description="Ratio of workers wearing helmets")
    active_violations: List[ViolationEvent] = Field(default_factory=list, description="Currently unresolved violations")
