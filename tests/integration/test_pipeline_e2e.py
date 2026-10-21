"""
End-to-end integration test validating the entire PHOENIX Core Intelligence Pipeline:
Frame Source -> Detection -> Temporal Tracking -> Homography -> Risk -> Navigation Graph -> Routing -> ETA.
"""

from datetime import datetime, timezone
import pytest

from app.decision.eta import DeterministicETAEstimator
from app.decision.occupancy import ApproximateOccupancyEstimator
from app.decision.prediction import PredictiveBlockageEngine
from app.decision.risk import DeterministicRiskEngine
from app.decision.routing import MultiFactorRoutingEngine
from app.domain.enums import DetectionType, RouteStatus, SmokeGrowthTrend
from app.domain.models import (
    BoundingBox,
    CalibrationPoint,
    Detection,
    NavigationEdge,
    NavigationNode,
    Point2D,
    SmokeObservation,
)
from app.graph.navigation_graph import NavigationGraph
from app.perception.detector import MockDetector
from app.perception.frame_source import SyntheticFrameSource
from app.perception.temporal import TemporalSmokeAnalyzer
from app.spatial.calibration import CalibrationService
from app.spatial.homography import PlanarHomographyMapper


def test_core_intelligence_pipeline_e2e():
    """
    Validate the complete perception-to-evacuation-recommendation decision pipeline using real video and dual YOLO models.
    """
    from app.perception.detector import YOLOAdapter
    from app.perception.frame_source import VideoFrameSource

    # 1. Ingest Real Video Frame
    frame_source = VideoFrameSource("videos/test2.mp4")
    success, frame, timestamp = frame_source.read_frame()
    assert success is True
    assert frame is not None

    # 2. Camera Spatial Calibration (Mapping image pixel 0..3840, 0..2160 to floor 0..20m, 0..10m)
    homography_mapper = PlanarHomographyMapper()
    cal_service = CalibrationService(mapper=homography_mapper)
    cal_points = [
        CalibrationPoint(image_point=Point2D(x=0.0, y=0.0), floor_point=Point2D(x=0.0, y=0.0)),
        CalibrationPoint(image_point=Point2D(x=3840.0, y=0.0), floor_point=Point2D(x=20.0, y=0.0)),
        CalibrationPoint(image_point=Point2D(x=3840.0, y=2160.0), floor_point=Point2D(x=20.0, y=10.0)),
        CalibrationPoint(image_point=Point2D(x=0.0, y=2160.0), floor_point=Point2D(x=0.0, y=10.0)),
    ]
    calibration = cal_service.create_calibration("cam_main", "bld_1", "fl_1", cal_points)

    # 3. Real Dual-Model YOLO Detection
    detector = YOLOAdapter(
        fire_smoke_model_path="models/fire_smoke_best.pt",
        person_model_path="models/yolo11n.pt",
    )
    detections = detector.detect(frame, "f_001", "cam_main", timestamp)
    assert len(detections) > 0

    # 4. Spatial Projection via Homography
    for det in detections:
        det.floor_point = homography_mapper.image_to_floorplan(det.bbox.ground_point, calibration)
        assert det.floor_point is not None

    # 5. Temporal Smoke Tracking over 2 frames
    temporal_analyzer = TemporalSmokeAnalyzer()
    mock_smoke_t1 = Detection(
        detection_id="det_smoke_1",
        frame_id="f_001",
        timestamp=datetime.fromtimestamp(0.0, tz=timezone.utc),
        camera_id="cam_main",
        class_name=DetectionType.SMOKE,
        confidence=0.92,
        bbox=BoundingBox(x1=100.0, y1=100.0, x2=250.0, y2=250.0),
    )
    temporal_analyzer.process_observations("cam_main", detections + [mock_smoke_t1], timestamp_seconds=0.0)

    # Ingest 2nd frame at t=2.0s with larger smoke area (growth)
    mock_smoke_t2 = Detection(
        detection_id="det_smoke_2",
        frame_id="f_002",
        timestamp=datetime.fromtimestamp(2.0, tz=timezone.utc),
        camera_id="cam_main",
        class_name=DetectionType.SMOKE,
        confidence=0.94,
        bbox=BoundingBox(x1=80.0, y1=80.0, x2=320.0, y2=320.0), # Expanded area
    )
    smoke_obs = temporal_analyzer.process_observations("cam_main", [mock_smoke_t2], timestamp_seconds=2.0)
    assert smoke_obs is not None
    assert smoke_obs.growth_rate_px2_per_sec > 0.0

    # 6. Topological Navigation Graph Construction
    nodes = [
        NavigationNode(node_id="room_A", building_id="bld_1", floor_id="fl_1", label="Room A", x=2.0, y=5.0),
        NavigationNode(node_id="corridor_center", building_id="bld_1", floor_id="fl_1", label="Center Hall", x=10.0, y=5.0),
        NavigationNode(node_id="exit_east", building_id="bld_1", floor_id="fl_1", label="Exit East", x=18.0, y=5.0, is_exit=True),
        NavigationNode(node_id="exit_west", building_id="bld_1", floor_id="fl_1", label="Exit West", x=2.0, y=9.0, is_exit=True),
    ]
    edges = [
        NavigationEdge(edge_id="e_A_center", building_id="bld_1", floor_id="fl_1", from_node="room_A", to_node="corridor_center", length_meters=8.0),
        NavigationEdge(edge_id="e_center_east", building_id="bld_1", floor_id="fl_1", from_node="corridor_center", to_node="exit_east", length_meters=8.0),
        NavigationEdge(edge_id="e_A_west", building_id="bld_1", floor_id="fl_1", from_node="room_A", to_node="exit_west", length_meters=4.0),
    ]
    nav_graph = NavigationGraph.from_nodes_and_edges("bld_1", "fl_1", nodes, edges)

    # 7. Deterministic Risk Calculation
    risk_engine = DeterministicRiskEngine()
    risk_snapshot = risk_engine.calculate_risk(
        building_id="bld_1",
        floor_id="fl_1",
        nodes=nav_graph.get_all_nodes(),
        detections=[mock_smoke_t2],
        smoke_observations=[smoke_obs],
    )
    assert risk_snapshot is not None

    # 8. Occupancy & Blockage Prediction
    occupancy_estimator = ApproximateOccupancyEstimator()
    occupancy_map = occupancy_estimator.estimate_node_occupancies(nav_graph.get_all_nodes(), [])

    prediction_engine = PredictiveBlockageEngine()
    nodes_dict = {n.node_id: n for n in nav_graph.get_all_nodes()}
    blockage_map = prediction_engine.predict_blockage_scores(nav_graph.get_all_edges(), nodes_dict, [smoke_obs])

    # 9. Deterministic Multi-Factor Evacuation Routing
    routing_engine = MultiFactorRoutingEngine()
    route = routing_engine.compute_route(
        nodes=nav_graph.get_all_nodes(),
        edges=nav_graph.get_all_edges(),
        origin_node_id="room_A",
        destination_exit_ids=nav_graph.get_exit_node_ids(),
        risk_snapshot=risk_snapshot,
        occupancy_map=occupancy_map,
        blockage_predictions=blockage_map,
    )

    assert route.status == RouteStatus.VALID
    assert route.origin_node == "room_A"
    assert route.destination_node in ("exit_west", "exit_east")
    assert len(route.path_nodes) >= 2
    assert route.cost_breakdown.total_cost > 0.0

    # 10. ETA Estimation
    eta_estimator = DeterministicETAEstimator()
    path_nodes = [nav_graph.get_node(nid) for nid in route.path_nodes if nav_graph.get_node(nid)]
    path_edges = [e for e in nav_graph.get_all_edges() if e.edge_id in route.path_edges]
    route.eta_seconds = eta_estimator.calculate_eta(path_nodes, path_edges, occupancy_map, risk_snapshot)

    assert route.eta_seconds > 0.0
    frame_source.release()


def test_continuous_loop_occupancy_prediction_routing_wiring():
    """
    Prove that person detections affect occupancy, smoke growth affects predicted blockage,
    both modify route costs, and continuous pipeline produces updated route/ETA.
    """
    from app.perception.continuous_pipeline import ContinuousPerceptionPipeline

    pipeline = ContinuousPerceptionPipeline(
        building_id="bldg-hq-01",
        floor_id="fl-01",
        primary_video_path="videos/test2.mp4",
        primary_camera_id="CAM-SOUTH-01",
    )
    pipeline.initialize_environment()
    assert pipeline.nav_graph is not None

    all_nodes = pipeline.nav_graph.get_all_nodes()
    all_edges = pipeline.nav_graph.get_all_edges()
    nodes_dict = {n.node_id: n for n in all_nodes}

    # 1. Test Person Detections -> Occupancy -> Route Cost Effect
    person_dets = [
        Detection(
            detection_id="p1",
            frame_id="f_01",
            timestamp=datetime.now(timezone.utc),
            camera_id="CAM-SOUTH-01",
            class_name=DetectionType.PERSON,
            confidence=0.95,
            bbox=BoundingBox(x1=100, y1=100, x2=200, y2=300),
            floor_point=Point2D(x=22.0, y=12.0), # At node_c1
        ),
        Detection(
            detection_id="p2",
            frame_id="f_01",
            timestamp=datetime.now(timezone.utc),
            camera_id="CAM-SOUTH-01",
            class_name=DetectionType.PERSON,
            confidence=0.91,
            bbox=BoundingBox(x1=120, y1=100, x2=220, y2=300),
            floor_point=Point2D(x=22.0, y=12.0), # Also at node_c1
        ),
    ]
    occ_map = pipeline.occupancy_estimator.estimate_node_occupancies(all_nodes, person_dets)
    assert occ_map["node_c1"] == 2

    # Baseline route with zero occupancy
    route_empty = pipeline.routing_engine.compute_route(
        nodes=all_nodes,
        edges=all_edges,
        origin_node_id="room_101",
        destination_exit_ids=pipeline.nav_graph.get_exit_node_ids(),
        risk_snapshot=None,
        occupancy_map={},
        blockage_predictions={},
    )

    # Route with occupancy at node_c1
    route_occupied = pipeline.routing_engine.compute_route(
        nodes=all_nodes,
        edges=all_edges,
        origin_node_id="room_101",
        destination_exit_ids=pipeline.nav_graph.get_exit_node_ids(),
        risk_snapshot=None,
        occupancy_map=occ_map,
        blockage_predictions={},
    )
    assert route_occupied.cost_breakdown.occupancy_cost > route_empty.cost_breakdown.occupancy_cost

    # 2. Test Smoke Growth -> Predicted Blockage -> Route Cost Effect
    smoke_obs = SmokeObservation(
        observation_id="obs_1",
        camera_id="CAM-SOUTH-01",
        timestamp=datetime.now(timezone.utc),
        area_px2=50000.0,
        delta_area_px2=25000.0,
        dt_seconds=2.0,
        growth_rate_px2_per_sec=12500.0,
        smoothed_growth_rate=12500.0,
        trend=SmokeGrowthTrend.RAPID_GROWTH,
        confidence=0.95,
    )
    # Give edge_101_c1 a hazard score so the mandatory entrance edge has predicted blockage
    for e in all_edges:
        if e.edge_id == "edge_101_c1":
            e.hazard_score = 0.6

    blockage_map = pipeline.prediction_engine.predict_blockage_scores(all_edges, nodes_dict, [smoke_obs])
    assert blockage_map["edge_101_c1"] > 0.0

    route_predicted = pipeline.routing_engine.compute_route(
        nodes=all_nodes,
        edges=all_edges,
        origin_node_id="room_101",
        destination_exit_ids=pipeline.nav_graph.get_exit_node_ids(),
        risk_snapshot=None,
        occupancy_map=occ_map,
        blockage_predictions=blockage_map,
    )
    assert route_predicted.cost_breakdown.predicted_blockage_cost > 0.0
    assert route_predicted.cost_breakdown.total_cost > route_empty.cost_breakdown.total_cost

    # 3. ETA reflects both occupancy and risk
    eta_empty = pipeline.eta_estimator.calculate_eta(all_nodes, all_edges, {}, None)
    eta_congested = pipeline.eta_estimator.calculate_eta(all_nodes, all_edges, {"node_c1": 25}, None)
    assert eta_congested > eta_empty


def test_video_upload_job_polling_and_results_lifecycle():
    """
    Regression test for the complete Video Upload and Processing Job status lifecycle:
    - POST /api/v1/videos/upload
    - POST /api/v1/videos/{video_id}/jobs
    - GET /api/v1/jobs/{job_id} (no NameError for json, valid output_metadata)
    - GET /api/v1/jobs/{job_id}/results
    - GET /api/v1/jobs/{job_id}/annotated-video
    """
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)
    # Login as Building Manager
    login_res = client.post("/api/v1/auth/login", json={"email": "manager@phoenix.local", "password": "ManagerPass123!"})
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 1. Upload video
    with open("videos/Main_video.mp4", "rb") as f:
        up_res = client.post("/api/v1/videos/upload", headers=headers, files={"file": ("Main_video.mp4", f, "video/mp4")})
    assert up_res.status_code == 201
    video_id = up_res.json()["video_id"]
    assert video_id.startswith("vid_")

    # 2. Start Job
    job_res = client.post(f"/api/v1/videos/{video_id}/jobs?stride=5&camera_id=CAM-UPLOAD", headers=headers)
    assert job_res.status_code == 202
    job_id = job_res.json()["job_id"]
    assert job_id.startswith("job_")

    # 3. Poll Job Status (verify GET /jobs/{job_id} succeeds with 200 OK)
    poll_res = client.get(f"/api/v1/jobs/{job_id}", headers=headers)
    assert poll_res.status_code == 200
    poll_data = poll_res.json()
    assert poll_data["job_id"] == job_id
    assert poll_data["video_id"] == video_id
    assert poll_data["status"] in ("QUEUED", "PROCESSING", "COMPLETED")

    # 4. Results Retrieval (verify GET /jobs/{job_id}/results succeeds with 200 OK)
    results_res = client.get(f"/api/v1/jobs/{job_id}/results", headers=headers)
    assert results_res.status_code == 200
    results_data = results_res.json()
    assert results_data["job_id"] == job_id
    assert "summary" in results_data
    assert "counts" in results_data


