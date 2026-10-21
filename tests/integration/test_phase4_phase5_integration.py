"""
Focused End-to-End Integration Test for Phase 4 & Phase 5:
Detection -> Ground Contact Point -> Homography Projection -> RiskEngine -> HeatmapGenerator.
Uses synthetic domain objects without YOLO or real video inference.
"""

from datetime import datetime, timezone
import numpy as np
import pytest

from app.domain.enums import DetectionType, RiskLevel, SmokeGrowthTrend
from app.domain.models import BoundingBox, CalibrationPoint, Detection, NavigationNode, Point2D, SmokeObservation
from app.spatial.calibration import CalibrationService
from app.spatial.heatmap import SpatialHeatmapGenerator
from app.spatial.homography import PlanarHomographyMapper
from app.decision.risk import DeterministicRiskEngine


def test_phase4_phase5_integration_pipeline_and_determinism():
    """
    Validate the complete Phase 4 & 5 backend chain:
    Synthetic Detection
    -> Representative Ground Point
    -> Planar Homography Projection
    -> Deterministic Spatial Risk Engine
    -> Spatial Heatmap Generator
    """
    # 1. Setup Camera Homography Calibration
    mapper = PlanarHomographyMapper()
    cal_service = CalibrationService(mapper=mapper)
    cal_points = [
        CalibrationPoint(image_point=Point2D(x=0.0, y=0.0), floor_point=Point2D(x=0.0, y=0.0)),
        CalibrationPoint(image_point=Point2D(x=640.0, y=0.0), floor_point=Point2D(x=20.0, y=0.0)),
        CalibrationPoint(image_point=Point2D(x=640.0, y=480.0), floor_point=Point2D(x=20.0, y=10.0)),
        CalibrationPoint(image_point=Point2D(x=0.0, y=480.0), floor_point=Point2D(x=0.0, y=10.0)),
    ]
    calibration = cal_service.create_calibration("cam_north", "bldg_1", "fl_1", cal_points)
    assert calibration.is_valid is True

    # 2. Synthetic Detections (Fire + Smoke)
    fire_det = Detection(
        detection_id="det_fire_01",
        frame_id="f_100",
        timestamp=datetime.fromtimestamp(10.0, tz=timezone.utc),
        camera_id="cam_north",
        class_name=DetectionType.FIRE,
        confidence=0.95,
        bbox=BoundingBox(x1=300.0, y1=200.0, x2=340.0, y2=480.0), # Bottom-center ground_point = (320, 480)
    )

    # 3. Phase 4 Representative Point & Homography Projection
    # Note: ground_point is used (bottom-center of bounding box for contact with floor)
    ground_pt = fire_det.bbox.ground_point
    assert ground_pt.x == 320.0
    assert ground_pt.y == 480.0

    floor_pt = mapper.image_to_floorplan(ground_pt, calibration)
    fire_det.floor_point = floor_pt
    assert abs(floor_pt.x - 10.0) < 0.1
    assert abs(floor_pt.y - 10.0) < 0.1

    # 4. Phase 5 Spatial Risk Snapshot Calculation
    nodes = [
        NavigationNode(node_id="node_hazard_center", building_id="bldg_1", floor_id="fl_1", label="Hazard Spot", x=10.0, y=10.0),
        NavigationNode(node_id="node_safe_exit", building_id="bldg_1", floor_id="fl_1", label="Safe Exit", x=0.0, y=0.0, is_exit=True),
    ]

    smoke_obs = SmokeObservation(
        observation_id="obs_01",
        camera_id="cam_north",
        timestamp=datetime.fromtimestamp(10.0, tz=timezone.utc),
        area_px2=8000.0,
        trend=SmokeGrowthTrend.RAPID_GROWTH,
    )

    risk_engine = DeterministicRiskEngine()

    # Run 1
    snapshot1 = risk_engine.calculate_risk(
        building_id="bldg_1",
        floor_id="fl_1",
        nodes=nodes,
        detections=[fire_det],
        smoke_observations=[smoke_obs],
    )

    # Run 2 (Determinism Verification)
    snapshot2 = risk_engine.calculate_risk(
        building_id="bldg_1",
        floor_id="fl_1",
        nodes=nodes,
        detections=[fire_det],
        smoke_observations=[smoke_obs],
    )

    assert snapshot1.node_risks == snapshot2.node_risks
    assert snapshot1.global_risk_level == snapshot2.global_risk_level == RiskLevel.CRITICAL
    assert snapshot1.node_risks["node_hazard_center"] == 1.0
    assert snapshot1.node_risks["node_safe_exit"] < 0.05

    # 5. Phase 5 Heatmap Generation
    heatmap_gen = SpatialHeatmapGenerator()
    hazards = [(fire_det.floor_point, snapshot1.node_risks["node_hazard_center"])]

    grid1 = heatmap_gen.generate_grid("fl_1", width_meters=20.0, height_meters=10.0, hazards=hazards)
    grid2 = heatmap_gen.generate_grid("fl_1", width_meters=20.0, height_meters=10.0, hazards=hazards)

    assert grid1.grid_values == grid2.grid_values
    assert grid1.rows == 20
    assert grid1.cols == 40
    assert grid1.grid_values[20 - 1][20 - 1] > 0.9 # Center cell high intensity
