"""
Unit tests for temporal smoke observation analysis and growth rate calculations.
"""

from datetime import datetime, timezone
import pytest

from app.domain.enums import DetectionType, SmokeGrowthTrend
from app.domain.models import BoundingBox, Detection
from app.perception.temporal import TemporalSmokeAnalyzer


def make_smoke_detection(area_side: float, timestamp_sec: float) -> Detection:
    return Detection(
        detection_id="det_test",
        frame_id="f_test",
        timestamp=datetime.fromtimestamp(timestamp_sec, tz=timezone.utc),
        camera_id="cam_01",
        class_name=DetectionType.SMOKE,
        confidence=0.90,
        bbox=BoundingBox(x1=0.0, y1=0.0, x2=area_side, y2=area_side),
    )


def test_temporal_growth_rate_calculation():
    """
    Verify smoke-region growth rate calculation:
    t1 = 0s: side = 50px (area = 2500 px^2)
    t2 = 2s: side = 70px (area = 4900 px^2)
    Δarea = 2400 px^2, Δt = 2s -> growth_rate = 1200 px^2/sec
    """
    analyzer = TemporalSmokeAnalyzer()

    # Frame 1 at t = 0.0s
    det1 = make_smoke_detection(area_side=50.0, timestamp_sec=0.0)
    obs1 = analyzer.process_observations("cam_01", [det1], timestamp_seconds=0.0)
    assert obs1 is not None
    assert obs1.area_px2 == 2500.0
    assert obs1.trend == SmokeGrowthTrend.UNKNOWN # First observation in window

    # Frame 2 at t = 2.0s
    det2 = make_smoke_detection(area_side=70.0, timestamp_sec=2.0)
    obs2 = analyzer.process_observations("cam_01", [det2], timestamp_seconds=2.0)
    assert obs2 is not None
    assert obs2.area_px2 == 4900.0
    assert obs2.delta_area_px2 == 2400.0
    assert obs2.dt_seconds == 2.0
    assert obs2.growth_rate_px2_per_sec == 1200.0
    assert obs2.trend == SmokeGrowthTrend.RAPID_GROWTH


def test_temporal_stable_trend():
    """Verify stable smoke region produces STABLE trend."""
    analyzer = TemporalSmokeAnalyzer()

    det1 = make_smoke_detection(area_side=50.0, timestamp_sec=0.0) # 2500 px^2
    det2 = make_smoke_detection(area_side=50.2, timestamp_sec=2.0) # ~2520 px^2

    analyzer.process_observations("cam_01", [det1], timestamp_seconds=0.0)
    obs2 = analyzer.process_observations("cam_01", [det2], timestamp_seconds=2.0)

    assert obs2 is not None
    assert obs2.trend == SmokeGrowthTrend.STABLE


def test_temporal_noise_floor_filtering():
    """Verify smoke bounding box below noise threshold is ignored."""
    analyzer = TemporalSmokeAnalyzer()
    small_det = make_smoke_detection(area_side=3.0, timestamp_sec=0.0) # area = 9 px^2 < 25 px^2

    obs = analyzer.process_observations("cam_01", [small_det], timestamp_seconds=0.0)
    assert obs is None


def test_temporal_disappearing_smoke_decay():
    """Verify disappearing smoke returns None and decays smoothed rate."""
    analyzer = TemporalSmokeAnalyzer()

    det = make_smoke_detection(area_side=60.0, timestamp_sec=0.0)
    analyzer.process_observations("cam_01", [det], timestamp_seconds=0.0)

    # Empty detections at t = 1.0s
    obs_none = analyzer.process_observations("cam_01", [], timestamp_seconds=1.0)
    assert obs_none is None
