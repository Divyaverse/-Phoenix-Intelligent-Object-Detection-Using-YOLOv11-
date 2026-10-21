"""
Integration test connecting FrameSource -> Detector -> TemporalSmokeAnalyzer.
Verifies frame acquisition, detection, and temporal smoke growth analysis.
"""

import pytest
from app.domain.enums import DetectionType, SmokeGrowthTrend
from app.domain.models import BoundingBox, Detection
from app.perception.detector import MockDetector
from app.perception.frame_source import SyntheticFrameSource
from app.perception.temporal import TemporalSmokeAnalyzer


def test_frame_source_to_detector_to_temporal_integration():
    """
    Validate the continuous pipeline:
    SyntheticFrameSource (Frame 1 & 2)
    -> MockDetector (Smoke region growth)
    -> TemporalSmokeAnalyzer (Computes SmokeObservation with growth rate)
    """
    # 1. Initialize Frame Source
    source = SyntheticFrameSource(width=640, height=480, max_frames=2, fps=1.0)
    assert source.is_opened() is True

    # 2. Setup Mock Detections for t=0.0s (Area = 2500 px^2) and t=1.0s (Area = 4900 px^2)
    det_t1 = Detection(
        detection_id="det_smoke_t1",
        frame_id="f_001",
        camera_id="cam_main",
        class_name=DetectionType.SMOKE,
        confidence=0.92,
        bbox=BoundingBox(x1=100.0, y1=100.0, x2=150.0, y2=150.0), # 50x50 = 2500
    )
    det_t2 = Detection(
        detection_id="det_smoke_t2",
        frame_id="f_002",
        camera_id="cam_main",
        class_name=DetectionType.SMOKE,
        confidence=0.95,
        bbox=BoundingBox(x1=90.0, y1=90.0, x2=160.0, y2=160.0), # 70x70 = 4900
    )

    detector = MockDetector(predefined_detections=[det_t1])
    temporal_analyzer = TemporalSmokeAnalyzer()

    # 3. Step 1: Read Frame 1 at t=0.0s
    success1, frame1, ts1 = source.read_frame()
    assert success1 is True
    assert ts1 == 0.0

    detections1 = detector.detect(frame1, "f_001", "cam_main", ts1)
    assert len(detections1) == 1
    assert detections1[0].class_name == DetectionType.SMOKE

    obs1 = temporal_analyzer.process_observations("cam_main", detections1, timestamp_seconds=ts1)
    assert obs1 is not None
    assert obs1.area_px2 == 2500.0
    assert obs1.trend == SmokeGrowthTrend.UNKNOWN

    # 4. Step 2: Read Frame 2 at t=1.0s with enlarged smoke bbox
    detector = MockDetector(predefined_detections=[det_t2])
    success2, frame2, ts2 = source.read_frame()
    assert success2 is True
    assert ts2 == 1.0

    detections2 = detector.detect(frame2, "f_002", "cam_main", ts2)
    assert len(detections2) == 1

    obs2 = temporal_analyzer.process_observations("cam_main", detections2, timestamp_seconds=ts2)
    assert obs2 is not None
    assert obs2.area_px2 == 4900.0
    assert obs2.delta_area_px2 == 2400.0
    assert obs2.dt_seconds == 1.0
    assert obs2.growth_rate_px2_per_sec == 2400.0
    assert obs2.trend == SmokeGrowthTrend.RAPID_GROWTH

    source.release()
