from __future__ import annotations

import time
from abc import ABC, abstractmethod
from typing import List, Tuple
import numpy as np

from perception.schemas.detection import BoundingBox, DetectionResult


class BaseDetector(ABC):
    """
    Abstract Base Class for object detectors in the civil engineering safety system.
    Decouples business logic and tracking from specific model frameworks (YOLOv5, Ultralytics, ONNX, etc.).
    """

    @abstractmethod
    def load_model(self, weights_path: str, device: str = "cpu") -> None:
        """Loads model weights onto target device."""
        pass

    @abstractmethod
    def detect(
        self,
        image: np.ndarray,
        conf_threshold: float = 0.4,
        iou_threshold: float = 0.5,
    ) -> DetectionResult:
        """
        Runs object detection on a single BGR image.
        :param image: numpy array of shape (H, W, 3), BGR format
        :param conf_threshold: minimum confidence score to keep box
        :param iou_threshold: NMS IoU threshold
        :return: DetectionResult schema object
        """
        pass


class MockDetector(BaseDetector):
    """
    Deterministic Mock Detector used for unit tests, CI pipelines, and CPU smoke testing.
    Outputs simulated person, head, and helmet detections without requiring CUDA or large .pt weights.
    """

    def __init__(self, predefined_boxes: List[BoundingBox] | None = None) -> None:
        self.predefined_boxes = predefined_boxes or []
        self.device = "cpu"
        self.is_loaded = False

    def load_model(self, weights_path: str, device: str = "cpu") -> None:
        self.device = device
        self.is_loaded = True

    def detect(
        self,
        image: np.ndarray,
        conf_threshold: float = 0.4,
        iou_threshold: float = 0.5,
    ) -> DetectionResult:
        h, w = image.shape[:2]
        boxes = []
        if self.predefined_boxes:
            boxes = [b for b in self.predefined_boxes if b.conf >= conf_threshold]
        else:
            # Generate deterministic mock detections in image center
            boxes = [
                BoundingBox(
                    x1=w * 0.4,
                    y1=h * 0.2,
                    x2=w * 0.6,
                    y2=h * 0.8,
                    conf=0.92,
                    class_id=0,
                    class_name="person",
                ),
                BoundingBox(
                    x1=w * 0.45,
                    y1=h * 0.2,
                    x2=w * 0.55,
                    y2=h * 0.35,
                    conf=0.88,
                    class_id=2,
                    class_name="helmet",
                ),
            ]

        return DetectionResult(
            frame_id=1,
            timestamp=time.monotonic(),
            boxes=boxes,
            inference_time_ms=5.0,
        )
