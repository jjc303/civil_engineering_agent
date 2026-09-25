from __future__ import annotations

import os
import sys
import time
from pathlib import Path
from typing import List, Optional
import cv2
import numpy as np
import torch

from perception.detectors.base import BaseDetector
from perception.schemas.detection import BoundingBox, DetectionResult


class LegacyYOLOv5Adapter(BaseDetector):
    """
    Adapter pattern implementation that wraps Smart_Construction's native YOLOv5 v2.x models
    without altering any internal Smart_Construction source code.
    """

    def __init__(self, weights_path: Optional[str] = None, device: str = "cpu"):
        self.device_str = device
        self.device = torch.device("cpu")
        self.model = None
        self.half = False
        self.names = ["person", "head", "helmet"]
        self.img_size = 640
        self.weights_path = weights_path

        # Add self-contained yolov5_legacy to sys.path for internal imports
        self.legacy_root = Path(__file__).resolve().parent / "yolov5_legacy"
        if str(self.legacy_root) not in sys.path:
            sys.path.insert(0, str(self.legacy_root))

        if weights_path and Path(weights_path).is_file():
            self.load_model(weights_path, device)

    def load_model(self, weights_path: str, device: str = "cpu") -> None:
        p = Path(weights_path)
        if not p.is_file():
            raise FileNotFoundError(f"Model weight file not found: {weights_path}")

        from models.experimental import attempt_load
        from utils.torch_utils import select_device
        from utils.utils import check_img_size

        self.device = select_device(device if device != "cpu" else "cpu")
        self.half = self.device.type != "cpu"

        # Load weights with PyTorch 2.6+ backward compatibility
        try:
            ckpt = torch.load(str(p), map_location=self.device, weights_only=False)
        except TypeError:
            ckpt = torch.load(str(p), map_location=self.device)
        self.model = ckpt["model"].float().fuse().eval()
        self.img_size = check_img_size(self.img_size, s=self.model.stride.max())

        if self.half:
            self.model.half()

        self.names = self.model.module.names if hasattr(self.model, "module") else self.model.names
        self.model.eval()

    def detect(
        self,
        image: np.ndarray,
        conf_threshold: float = 0.4,
        iou_threshold: float = 0.5,
    ) -> DetectionResult:
        if self.model is None:
            raise RuntimeError("Model is not loaded. Call load_model(weights_path) first.")

        from utils.datasets import letterbox
        from utils.utils import non_max_suppression, scale_coords

        t0 = time.monotonic()
        img0 = image.copy()

        # Preprocess using letterbox
        img = letterbox(img0, new_shape=self.img_size)[0]
        img = img[:, :, ::-1].transpose(2, 0, 1)  # BGR to RGB, to 3xHxW
        img = np.ascontiguousarray(img)

        img_tensor = torch.from_numpy(img).to(self.device)
        img_tensor = img_tensor.half() if self.half else img_tensor.float()
        img_tensor /= 255.0
        if img_tensor.ndimension() == 3:
            img_tensor = img_tensor.unsqueeze(0)

        # Forward pass
        t_infer_start = time.monotonic()
        with torch.no_grad():
            pred = self.model(img_tensor)[0]
            pred = non_max_suppression(pred, conf_threshold, iou_threshold)
        t_infer_end = time.monotonic()

        boxes: List[BoundingBox] = []
        for det in pred:
            if det is not None and len(det):
                det[:, :4] = scale_coords(img_tensor.shape[2:], det[:, :4], img0.shape).round()
                for *xyxy, conf, cls in det:
                    class_id = int(cls)
                    class_name = self.names[class_id] if class_id < len(self.names) else f"class_{class_id}"
                    boxes.append(
                        BoundingBox(
                            x1=float(xyxy[0]),
                            y1=float(xyxy[1]),
                            x2=float(xyxy[2]),
                            y2=float(xyxy[3]),
                            conf=float(conf),
                            class_id=class_id,
                            class_name=class_name,
                        )
                    )

        return DetectionResult(
            frame_id=1,
            timestamp=time.monotonic(),
            boxes=boxes,
            inference_time_ms=(t_infer_end - t_infer_start) * 1000.0,
        )
