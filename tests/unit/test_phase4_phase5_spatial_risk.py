"""
Comprehensive unit tests for Phase 4 (Spatial Homography Mapping) and Phase 5 (Heatmap & Spatial Risk Engine).
Includes robust edge case testing, invalid calibration failures, and out-of-bounds mapping tests.
"""

from datetime import datetime, timezone
import numpy as np
import pytest

from app.core.errors import InvalidCalibrationError, SpatialMappingUnavailableError
from app.domain.enums import DetectionType, RiskLevel, SmokeGrowthTrend
from app.domain.models import BoundingBox, CalibrationPoint, Detection, NavigationNode, Point2D, SmokeObservation
from app.spatial.calibration import CalibrationService
from app.spatial.heatmap import SpatialHeatmapGenerator
from app.spatial.homography import PlanarHomographyMapper
from app.decision.risk import DeterministicRiskEngine


# --- PHASE 4 TESTS ---

def test_phase4_valid_homography_mapping():
    """Test 1 & 2: Valid known homography with multiple points."""
    mapper = PlanarHomographyMapper()
    service = CalibrationService(mapper=mapper)

    points = [
        CalibrationPoint(image_point=Point2D(x=0.0, y=0.0), floor_point=Point2D(x=0.0, y=0.0)),
        CalibrationPoint(image_point=Point2D(x=640.0, y=0.0), floor_point=Point2D(x=10.0, y=0.0)),
        CalibrationPoint(image_point=Point2D(x=640.0, y=480.0), floor_point=Point2D(x=10.0, y=8.0)),
        CalibrationPoint(image_point=Point2D(x=0.0, y=480.0), floor_point=Point2D(x=0.0, y=8.0)),
    ]
    cal = service.create_calibration("cam_1", "bld_1", "fl_1", points)

    assert cal.is_valid is True
    assert cal.reprojection_error < 0.1

    # Image point (320, 480) ground point -> floor (5.0, 8.0)
    mapped = mapper.image_to_floorplan(Point2D(x=320.0, y=480.0), cal)
    assert abs(mapped.x - 5.0) < 0.05
    assert abs(mapped.y - 8.0) < 0.05


def test_phase4_identity_transform():
    """Test 3: Identity/simple scale transform mapping."""
    mapper = PlanarHomographyMapper()
    service = CalibrationService(mapper=mapper)

    points = [
        CalibrationPoint(image_point=Point2D(x=0.0, y=0.0), floor_point=Point2D(x=0.0, y=0.0)),
        CalibrationPoint(image_point=Point2D(x=100.0, y=0.0), floor_point=Point2D(x=100.0, y=0.0)),
        CalibrationPoint(image_point=Point2D(x=100.0, y=100.0), floor_point=Point2D(x=100.0, y=100.0)),
        CalibrationPoint(image_point=Point2D(x=0.0, y=100.0), floor_point=Point2D(x=0.0, y=100.0)),
    ]
    cal = service.create_calibration("cam_1", "bld_1", "fl_1", points)
    mapped = mapper.image_to_floorplan(Point2D(x=50.0, y=50.0), cal)
    assert mapped.x == 50.0
    assert mapped.y == 50.0


def test_phase4_insufficient_points_fails():
    """Test 5: Less than 4 points raises InvalidCalibrationError."""
    mapper = PlanarHomographyMapper()
    points = [
        CalibrationPoint(image_point=Point2D(x=0.0, y=0.0), floor_point=Point2D(x=0.0, y=0.0)),
        CalibrationPoint(image_point=Point2D(x=10.0, y=0.0), floor_point=Point2D(x=1.0, y=0.0)),
    ]
    with pytest.raises(InvalidCalibrationError, match="Insufficient calibration points"):
        mapper.compute_calibration_matrix(points)


def test_phase4_collinear_degenerate_points_fails():
    """Test 6: Collinear points raise InvalidCalibrationError."""
    mapper = PlanarHomographyMapper()
    points = [
        CalibrationPoint(image_point=Point2D(x=0.0, y=0.0), floor_point=Point2D(x=0.0, y=0.0)),
        CalibrationPoint(image_point=Point2D(x=10.0, y=10.0), floor_point=Point2D(x=1.0, y=1.0)),
        CalibrationPoint(image_point=Point2D(x=20.0, y=20.0), floor_point=Point2D(x=2.0, y=2.0)),
        CalibrationPoint(image_point=Point2D(x=30.0, y=30.0), floor_point=Point2D(x=3.0, y=3.0)),
    ]
    with pytest.raises(InvalidCalibrationError):
        mapper.compute_calibration_matrix(points)


def test_phase4_out_of_bounds_image_point():
    """Test 9: Out-of-bounds image point maps deterministically without crashing."""
    mapper = PlanarHomographyMapper()
    service = CalibrationService(mapper=mapper)
    points = [
        CalibrationPoint(image_point=Point2D(x=0.0, y=0.0), floor_point=Point2D(x=0.0, y=0.0)),
        CalibrationPoint(image_point=Point2D(x=640.0, y=0.0), floor_point=Point2D(x=10.0, y=0.0)),
        CalibrationPoint(image_point=Point2D(x=640.0, y=480.0), floor_point=Point2D(x=10.0, y=8.0)),
        CalibrationPoint(image_point=Point2D(x=0.0, y=480.0), floor_point=Point2D(x=0.0, y=8.0)),
    ]
    cal = service.create_calibration("cam_1", "bld_1", "fl_1", points)

    # Point outside 640x480 boundary
    oob_pt = Point2D(x=1280.0, y=960.0)
    mapped = mapper.image_to_floorplan(oob_pt, cal)
    assert mapped.x == 20.0
    assert mapped.y == 16.0


def test_phase4_deterministic_repeated_mapping():
    """Test 10: Repeated mapping produces identical coordinates."""
    mapper = PlanarHomographyMapper()
    service = CalibrationService(mapper=mapper)
    points = [
        CalibrationPoint(image_point=Point2D(x=0.0, y=0.0), floor_point=Point2D(x=0.0, y=0.0)),
        CalibrationPoint(image_point=Point2D(x=640.0, y=0.0), floor_point=Point2D(x=10.0, y=0.0)),
        CalibrationPoint(image_point=Point2D(x=640.0, y=480.0), floor_point=Point2D(x=10.0, y=8.0)),
        CalibrationPoint(image_point=Point2D(x=0.0, y=480.0), floor_point=Point2D(x=0.0, y=8.0)),
    ]
    cal = service.create_calibration("cam_1", "bld_1", "fl_1", points)
    pt = Point2D(x=123.45, y=267.89)

    m1 = mapper.image_to_floorplan(pt, cal)
    m2 = mapper.image_to_floorplan(pt, cal)
    assert m1.x == m2.x
    assert m1.y == m2.y


# --- PHASE 5 TESTS ---

def test_phase5_risk_empty_detections():
    """Verify empty detections produce 0.0 risk and LOW global level."""
    engine = DeterministicRiskEngine()
    nodes = [NavigationNode(node_id="n1", building_id="b1", floor_id="f1", label="Node 1", x=5.0, y=5.0)]

    snapshot = engine.calculate_risk("b1", "f1", nodes, detections=[], smoke_observations=[])
    assert snapshot.node_risks["n1"] == 0.0
    assert snapshot.global_risk_level == RiskLevel.LOW
    assert snapshot.active_hazards_count == 0


def test_phase5_risk_fire_smoke_and_temporal_decay():
    """Verify fire and smoke detections produce bounded deterministic risk scores."""
    engine = DeterministicRiskEngine()
    nodes = [
        NavigationNode(node_id="n_close", building_id="b1", floor_id="f1", label="Close Node", x=5.0, y=5.0),
        NavigationNode(node_id="n_far", building_id="b1", floor_id="f1", label="Far Node", x=25.0, y=25.0),
    ]

    fire_det = Detection(
        detection_id="d1",
        frame_id="f1",
        timestamp=datetime.now(timezone.utc),
        camera_id="cam1",
        class_name=DetectionType.FIRE,
        confidence=0.90,
        bbox=BoundingBox(x1=0, y1=0, x2=10, y2=10),
        floor_point=Point2D(x=5.0, y=5.0),
    )

    smoke_obs = SmokeObservation(
        observation_id="o1",
        camera_id="cam1",
        timestamp=datetime.now(timezone.utc),
        area_px2=5000.0,
        trend=SmokeGrowthTrend.RAPID_GROWTH, # 1.5x risk multiplier
    )

    snapshot = engine.calculate_risk("b1", "f1", nodes, detections=[fire_det], smoke_observations=[smoke_obs])

    # n_close at distance=0: risk = 1.0 (base) * 0.90 (conf) * 1.5 (growth) * exp(0) = 1.35 -> clipped to 1.0
    assert snapshot.node_risks["n_close"] == 1.0
    # n_far at distance ~28.28m: exponential decay reduces risk drastically
    assert snapshot.node_risks["n_far"] < 0.1
    assert snapshot.global_risk_level == RiskLevel.CRITICAL
    assert snapshot.active_hazards_count == 1


def test_phase5_heatmap_generation_bounded_and_deterministic():
    """Verify heatmap grid generation produces bounded [0,1] values deterministically."""
    gen = SpatialHeatmapGenerator()

    # Empty hazards
    grid_empty = gen.generate_grid("f1", width_meters=10.0, height_meters=10.0, hazards=[])
    assert np.max(grid_empty.grid_values) == 0.0

    # Single hazard at center (5.0, 5.0) with intensity 0.8
    hazards = [(Point2D(x=5.0, y=5.0), 0.8)]
    grid1 = gen.generate_grid("f1", width_meters=10.0, height_meters=10.0, hazards=hazards)
    grid2 = gen.generate_grid("f1", width_meters=10.0, height_meters=10.0, hazards=hazards)

    assert grid1.grid_values == grid2.grid_values
    arr = np.array(grid1.grid_values)
    assert np.max(arr) <= 0.8
    assert np.min(arr) >= 0.0
