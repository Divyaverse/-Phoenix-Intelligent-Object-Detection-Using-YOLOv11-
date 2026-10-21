"""
Unit tests for deterministic risk engine scoring and heatmap generation.
"""

from datetime import datetime, timezone
import pytest

from app.decision.risk import DeterministicRiskEngine
from app.domain.enums import DetectionType, RiskLevel, SmokeGrowthTrend
from app.domain.models import BoundingBox, Detection, NavigationNode, Point2D, SmokeObservation
from app.spatial.heatmap import SpatialHeatmapGenerator


def test_deterministic_risk_engine_scoring():
    """Verify fire detection at node location yields high deterministic risk."""
    engine = DeterministicRiskEngine()

    nodes = [
        NavigationNode(node_id="n1", building_id="bld_1", floor_id="fl_1", label="Corridor A", x=5.0, y=5.0),
        NavigationNode(node_id="n2", building_id="bld_1", floor_id="fl_1", label="Corridor B", x=25.0, y=5.0),
    ]

    # Fire detection located at (5.0, 5.0) near n1
    fire_det = Detection(
        detection_id="det_fire",
        frame_id="f1",
        timestamp=datetime.now(timezone.utc),
        camera_id="cam_01",
        class_name=DetectionType.FIRE,
        confidence=0.95,
        bbox=BoundingBox(x1=100.0, y1=100.0, x2=200.0, y2=200.0),
        floor_point=Point2D(x=5.0, y=5.0),
    )

    snapshot = engine.calculate_risk(
        building_id="bld_1",
        floor_id="fl_1",
        nodes=nodes,
        detections=[fire_det],
        smoke_observations=[],
    )

    # Node n1 should have high risk (~0.95), while distant node n2 should have low risk
    assert snapshot.node_risks["n1"] > 0.80
    assert snapshot.node_risks["n2"] < 0.10
    assert snapshot.global_risk_level in (RiskLevel.CRITICAL, RiskLevel.HIGH)


def test_risk_growth_multiplier_amplification():
    """Verify rapid smoke growth increases risk intensity on nearby nodes."""
    engine = DeterministicRiskEngine()

    nodes = [
        NavigationNode(node_id="n1", building_id="bld_1", floor_id="fl_1", label="Corridor", x=10.0, y=10.0),
    ]

    smoke_det = Detection(
        detection_id="det_smoke",
        frame_id="f1",
        timestamp=datetime.now(timezone.utc),
        camera_id="cam_01",
        class_name=DetectionType.SMOKE,
        confidence=0.80,
        bbox=BoundingBox(x1=50.0, y1=50.0, x2=150.0, y2=150.0),
        floor_point=Point2D(x=10.0, y=10.0),
    )

    # Calculate baseline risk without growth
    snapshot_baseline = engine.calculate_risk("bld_1", "fl_1", nodes, [smoke_det], [])

    # Calculate risk with RAPID_GROWTH observation
    obs_rapid = SmokeObservation(
        observation_id="obs_1",
        camera_id="cam_01",
        area_px2=5000.0,
        delta_area_px2=2000.0,
        dt_seconds=2.0,
        growth_rate_px2_per_sec=1000.0,
        trend=SmokeGrowthTrend.RAPID_GROWTH,
        confidence=0.85,
    )
    snapshot_rapid = engine.calculate_risk("bld_1", "fl_1", nodes, [smoke_det], [obs_rapid])

    assert snapshot_rapid.node_risks["n1"] > snapshot_baseline.node_risks["n1"]


def test_spatial_heatmap_generator():
    """Verify 2D raster heatmap generation."""
    generator = SpatialHeatmapGenerator()
    hazards = [(Point2D(x=5.0, y=5.0), 0.90)]

    grid = generator.generate_grid(
        floor_id="fl_1",
        width_meters=20.0,
        height_meters=10.0,
        hazards=hazards,
    )

    assert grid.cols > 0
    assert grid.rows > 0
    assert len(grid.grid_values) == grid.rows
    assert len(grid.grid_values[0]) == grid.cols
    # Max intensity in grid should be approximately 0.90
    max_val = max(max(row) for row in grid.grid_values)
    assert abs(max_val - 0.90) < 0.05
