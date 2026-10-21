"""
Unit tests for perception: frame sources, detection schemas, confidence filtering, and mock detection.
"""

from datetime import datetime, timezone
import numpy as np
import pytest

from app.core.errors import ModelUnavailableError
from app.domain.enums import DetectionType
from app.domain.models import BoundingBox, Detection, Point2D
from app.perception.detector import MockDetector, YOLOAdapter
from app.perception.frame_source import SyntheticFrameSource


def test_synthetic_frame_source():
    """Verify synthetic frame generator produces sequential frames with monotonic timestamps."""
    source = SyntheticFrameSource(width=320, height=240, max_frames=5, fps=10.0)
    assert source.is_opened() is True

    frames_read = 0
    last_timestamp = -1.0

    while source.is_opened():
        success, frame, timestamp = source.read_frame()
        if not success:
            break
        frames_read += 1
        assert frame is not None
        assert frame.shape == (240, 320, 3)
        assert timestamp > last_timestamp
        last_timestamp = timestamp

    assert frames_read == 5
    source.release()
    assert source.is_opened() is False


def test_mock_detector_inference():
    """Verify detector returns structured detections matching schema."""
    det1 = Detection(
        detection_id="det_1",
        frame_id="f_1",
        timestamp=datetime.now(timezone.utc),
        camera_id="cam_01",
        class_name=DetectionType.FIRE,
        confidence=0.95,
        bbox=BoundingBox(x1=50.0, y1=50.0, x2=120.0, y2=150.0),
    )
    detector = MockDetector(predefined_detections=[det1])
    assert detector.is_ready() is True

    dummy_frame = np.zeros((480, 640, 3), dtype=np.uint8)
    results = detector.detect(dummy_frame, frame_id="f_1", camera_id="cam_01", timestamp_seconds=0.0)

    assert len(results) == 1
    assert results[0].class_name == DetectionType.FIRE
    assert results[0].confidence == 0.95
    assert results[0].bbox.area == 7000.0


def test_mock_detector_unavailable_fails():
    """Verify detector throws ModelUnavailableError when unready."""
    detector = MockDetector()
    detector.set_ready(False)

    dummy_frame = np.zeros((100, 100, 3), dtype=np.uint8)
    with pytest.raises(ModelUnavailableError):
        detector.detect(dummy_frame, frame_id="f_1", camera_id="cam_01", timestamp_seconds=0.0)


def test_yolo_adapter_missing_model_fails():
    """Verify real YOLO adapter raises ModelUnavailableError when model path is missing."""
    with pytest.raises(ModelUnavailableError, match="not found"):
        YOLOAdapter(model_path="models/non_existent_weights.pt")
