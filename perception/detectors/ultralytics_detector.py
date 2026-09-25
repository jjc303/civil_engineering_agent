from __future__ import annotations

import time
from pathlib import Path
from typing import List, Optional
import numpy as np
from ultralytics import YOLO

from perception.detectors.base import BaseDetector, get_optimal_device
from perception.schemas.detection import BoundingBox, DetectionResult


class UltralyticsDetector(BaseDetector):
    """
    Modern Detector implementation using the official Ultralytics (YOLOv8/v11) engine.
    Implements the BaseDetector interface, producing standardized DetectionResult outputs.
    """

    def __init__(self, weights_path: Optional[str] = None, device: Optional[str] = None):
        self.device = get_optimal_device(device)
        self.model: Optional[YOLO] = None
        self.names = {}
        self.weights_path = weights_path

        if weights_path and Path(weights_path).is_file():
            self.load_model(weights_path, self.device)

    def load_model(self, weights_path: str, device: Optional[str] = None) -> None:
        p = Path(weights_path)
        if not p.is_file():
            raise FileNotFoundError(f"Ultralytics model weight not found: {weights_path}")

        self.device = get_optimal_device(device or self.device)
        self.weights_path = str(p)
        self.model = YOLO(str(p))
        self.names = self.model.names if hasattr(self.model, "names") else {}

    def detect(
        self,
        image: np.ndarray,
        conf_threshold: float = 0.4,
        iou_threshold: float = 0.5,
    ) -> DetectionResult:
        if self.model is None:
            raise RuntimeError("Ultralytics model is not loaded. Call load_model() first.")

        t_start = time.monotonic()
        results = self.model.predict(
            source=image,
            conf=conf_threshold,
            iou=iou_threshold,
            device=self.device,
            verbose=False,
        )
        t_end = time.monotonic()

        boxes: List[BoundingBox] = []
        if results and len(results) > 0:
            det = results[0].boxes
            if det is not None and len(det) > 0:
                xyxy_arr = det.xyxy.cpu().numpy()
                conf_arr = det.conf.cpu().numpy()
                cls_arr = det.cls.cpu().numpy()

                for i in range(len(xyxy_arr)):
                    cls_id = int(cls_arr[i])
                    cls_name = self.names.get(cls_id, f"class_{cls_id}")
                    boxes.append(
                        BoundingBox(
                            x1=float(xyxy_arr[i][0]),
                            y1=float(xyxy_arr[i][1]),
                            x2=float(xyxy_arr[i][2]),
                            y2=float(xyxy_arr[i][3]),
                            conf=float(conf_arr[i]),
                            class_id=cls_id,
                            class_name=cls_name,
                        )
                    )

        return DetectionResult(
            frame_id=1,
            timestamp=time.monotonic(),
            boxes=boxes,
            inference_time_ms=(t_end - t_start) * 1000.0,
        )
