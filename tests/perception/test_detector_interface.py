import numpy as np
import pytest
from perception.detectors.base import BaseDetector, MockDetector
from perception.schemas.detection import BoundingBox, DetectionResult


def test_mock_detector_interface():
    detector: BaseDetector = MockDetector()
    detector.load_model("mock_weights.pt", device="cpu")

    dummy_image = np.zeros((480, 640, 3), dtype=np.uint8)
    result = detector.detect(dummy_image, conf_threshold=0.5)

    assert isinstance(result, DetectionResult)
    assert len(result.boxes) > 0
    assert result.inference_time_ms >= 0.0

    class_names = [b.class_name for b in result.boxes]
    assert "person" in class_names
    assert "helmet" in class_names
