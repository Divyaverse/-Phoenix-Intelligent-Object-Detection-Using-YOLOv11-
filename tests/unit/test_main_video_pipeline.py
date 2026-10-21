"""
Unit tests validating the complete processing pipeline, spatial mapping,
homography calibration, floorplan representation, and routing for videos/Main_video.mp4.
"""

import json
import os
import pytest
import numpy as np

from app.domain.enums import MeasurementProvenance, RouteStatus
from app.domain.models import CalibrationPoint, Point2D
from app.spatial.calibration import CalibrationService
from app.spatial.floorplan_parser import FloorplanProcessor
from app.spatial.homography import PlanarHomographyMapper
from app.decision.risk import DeterministicRiskEngine
from app.decision.routing import MultiFactorRoutingEngine
from app.decision.eta import DeterministicETAEstimator
from app.decision.occupancy import ApproximateOccupancyEstimator
from app.decision.prediction import PredictiveBlockageEngine


def test_main_corridor_floorplan_structure():
    """Verify the structural geometry and provenance of the Main_video floorplan."""
    processor = FloorplanProcessor()
    fp = processor.create_main_corridor_floorplan(building_id="bldg-main-01", floor_id="fl-01")

    assert fp.building_id == "bldg-main-01"
    assert fp.floor_id == "fl-01"
    assert fp.physical_width_meters == 32.0
    assert fp.physical_height_meters == 30.0
    assert fp.is_scale_calibrated is True

    # Nodes
    node_ids = {n.node_id for n in fp.nodes}
    assert "exit_south" in node_ids
    assert "exit_north" in node_ids
    assert "node_corridor_south" in node_ids
    assert "node_corridor_mid" in node_ids
    assert "node_corridor_north" in node_ids
    assert "node_east_alcove" in node_ids
    assert "node_west_suites" in node_ids

    # Exits
    exit_nodes = [n for n in fp.nodes if n.is_exit]
    assert len(exit_nodes) == 2

    # Edges
    assert len(fp.edges) == 6
    for e in fp.edges:
        assert e.length_meters > 0.0

    # Regions & Provenance
    measured_regions = [r for r in fp.regions if r.provenance == MeasurementProvenance.MEASURED.value]
    estimated_regions = [r for r in fp.regions if r.provenance == MeasurementProvenance.ESTIMATED.value]

    assert len(measured_regions) >= 3  # Corridor, alcove entrance, exits
    assert len(estimated_regions) >= 1 # West office suites behind glass


def test_main_video_tile_homography_calibration():
    """Verify ground-contact homography calibration on corridor floor tiles."""
    mapper = PlanarHomographyMapper()
    cal_service = CalibrationService(mapper=mapper)

    cal_points = [
        CalibrationPoint(image_point=Point2D(x=280.0, y=700.0), floor_point=Point2D(x=14.0, y=5.0)),
        CalibrationPoint(image_point=Point2D(x=820.0, y=700.0), floor_point=Point2D(x=18.0, y=5.0)),
        CalibrationPoint(image_point=Point2D(x=425.0, y=475.0), floor_point=Point2D(x=14.0, y=20.0)),
        CalibrationPoint(image_point=Point2D(x=575.0, y=475.0), floor_point=Point2D(x=18.0, y=20.0)),
    ]

    calibration = cal_service.create_calibration("CAM-MAIN-01", "bldg-main-01", "fl-01", cal_points)
    assert calibration.is_valid is True
    assert calibration.reprojection_error <= 1.0

    # Verify determinant & stability
    H = np.array(calibration.matrix_3x3)
    det = np.linalg.det(H)
    assert abs(det) > 1e-8

    # Project mid-corridor ground point
    mid_img = Point2D(x=550.0, y=700.0)
    mid_floor = mapper.image_to_floorplan(mid_img, calibration)
    assert 14.0 <= mid_floor.x <= 18.0
    assert 4.0 <= mid_floor.y <= 6.0


def test_mapping_verification_workflow():
    """Verify the mapping-confirmation workflow properly flags verified vs unverified elements."""
    mapper = PlanarHomographyMapper()
    cal_service = CalibrationService(mapper=mapper)

    cal_points = [
        CalibrationPoint(image_point=Point2D(x=280.0, y=700.0), floor_point=Point2D(x=14.0, y=5.0)),
        CalibrationPoint(image_point=Point2D(x=820.0, y=700.0), floor_point=Point2D(x=18.0, y=5.0)),
        CalibrationPoint(image_point=Point2D(x=425.0, y=475.0), floor_point=Point2D(x=14.0, y=20.0)),
        CalibrationPoint(image_point=Point2D(x=575.0, y=475.0), floor_point=Point2D(x=18.0, y=20.0)),
    ]

    calibration = cal_service.create_calibration("CAM-MAIN-01", "bldg-main-01", "fl-01", cal_points)
    verification = cal_service.verify_mapping(calibration)

    assert verification["is_valid"] is True
    assert verification["status"] == "VERIFIED"
    assert verification["reprojection_error_px"] <= 1.0
    assert "ground_corridor_plane" in verification["verified_elements"]
    assert "ceiling_smoke_layer_3d_depth" in verification["unverified_elements"]


def test_main_video_routing_with_east_hazard():
    """Verify deterministic routing guides occupants away from the East alcove hazard toward South exit."""
    processor = FloorplanProcessor()
    fp = processor.create_main_corridor_floorplan("bldg-main-01", "fl-01")

    from app.graph.navigation_graph import NavigationGraph
    nav_graph = NavigationGraph.from_nodes_and_edges("bldg-main-01", "fl-01", fp.nodes, fp.edges)

    risk_engine = DeterministicRiskEngine()
    routing_engine = MultiFactorRoutingEngine()
    eta_estimator = DeterministicETAEstimator()
    occupancy_estimator = ApproximateOccupancyEstimator()
    prediction_engine = PredictiveBlockageEngine()

    all_nodes = nav_graph.get_all_nodes()
    all_edges = nav_graph.get_all_edges()
    nodes_dict = {n.node_id: n for n in all_nodes}

    # Simulate critical risk at east alcove and high risk at north approach
    from app.domain.models import RiskSnapshot
    from app.domain.enums import RiskLevel
    from datetime import datetime, timezone

    mock_risk = RiskSnapshot(
        snapshot_id="test_snap",
        building_id="bldg-main-01",
        floor_id="fl-01",
        timestamp=datetime.now(timezone.utc),
        global_risk_level=RiskLevel.HIGH,
        node_risks={
            "node_east_alcove": 0.95,
            "node_corridor_north": 0.80,
            "node_corridor_mid": 0.35,
            "node_corridor_south": 0.05,
            "exit_south": 0.0,
            "exit_north": 0.85,
            "node_west_suites": 0.10,
        },
        active_hazards_count=2,
    )

    occ_map = occupancy_estimator.estimate_node_occupancies(all_nodes, [])
    blockage_map = prediction_engine.predict_blockage_scores(all_edges, nodes_dict, [])

    route = routing_engine.compute_route(
        nodes=all_nodes,
        edges=all_edges,
        origin_node_id="node_west_suites",
        destination_exit_ids=nav_graph.get_exit_node_ids(),
        risk_snapshot=mock_risk,
        occupancy_map=occ_map,
        blockage_predictions=blockage_map,
    )

    assert route.status == RouteStatus.VALID
    assert route.origin_node == "node_west_suites"
    # Should choose exit_south because exit_north and east corridor are hazard-compromised
    assert route.destination_node == "exit_south"
    assert "node_east_alcove" not in route.path_nodes

    path_nodes = [nav_graph.get_node(nid) for nid in route.path_nodes if nav_graph.get_node(nid)]
    path_edges = [e for e in all_edges if e.edge_id in route.path_edges]
    eta = eta_estimator.calculate_eta(path_nodes, path_edges, occ_map, mock_risk)
    assert eta > 0.0


def test_main_video_generated_artifacts_integrity():
    """Verify that actual statistics and detection records were genuinely generated and persisted."""
    stats_file = "evaluation/main_video_validation/statistics.json"
    dets_file = "evaluation/main_video_validation/detections.json"
    annotated_video = "videos/Main_video_annotated.mp4"

    assert os.path.isfile(stats_file), "statistics.json was not created"
    assert os.path.isfile(dets_file), "detections.json was not created"
    assert os.path.isfile(annotated_video), "Annotated video was not generated"

    with open(stats_file, "r", encoding="utf-8") as f:
        stats = json.load(f)

    assert stats["total_frames_processed"] == 240
    assert stats["detection_counts"]["fire"] > 500
    assert stats["detection_counts"]["smoke"] > 100
    assert stats["average_confidences"]["fire"] > 0.50
    assert stats["average_confidences"]["smoke"] > 0.45
    assert stats["spatial_calibration"]["status"] == "VALID"
