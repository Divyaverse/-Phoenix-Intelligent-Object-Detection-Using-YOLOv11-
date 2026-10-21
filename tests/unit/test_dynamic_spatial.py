"""
Comprehensive tests for PHOENIX Dynamic Floorplan, Video Geometry, Multi-Camera Spatial Fusion, and Scale Calibration.
"""

from datetime import datetime, timezone
import numpy as np
import pytest

from app.domain.enums import (
    DetectionType,
    MeasurementProvenance,
    RouteStatus,
    SpatialRegionType,
)
from app.domain.models import (
    BoundingBox,
    Calibration,
    Detection,
    FloorHazardObservation,
    FloorplanModel,
    NavigationEdge,
    NavigationNode,
    Point2D,
    ScaleReference,
    SpatialRegion,
)
from app.spatial.floorplan_parser import FloorplanProcessor
from app.spatial.video_geometry import VideoGeometryExtractor
from app.spatial.multi_camera_fusion import MultiCameraSpatialFusionEngine
from app.spatial.spatial_manager import SpatialManager
from app.decision.routing import MultiFactorRoutingEngine
from app.decision.risk import DeterministicRiskEngine


class TestFloorplanCalibrationAndExtraction:
    """Test dynamic scale calibration, region extraction, and graph topology generation."""

    def test_scale_calibration_with_known_distance(self):
        processor = FloorplanProcessor()
        # User provides reference: (100, 100) to (500, 100) is 20 meters (400 px = 20m => 0.05 m/px)
        p1 = Point2D(x=100.0, y=100.0)
        p2 = Point2D(x=500.0, y=100.0)
        scale_ref = processor.calibrate_scale(p1, p2, known_distance_meters=20.0)

        assert scale_ref.is_calibrated is True
        assert scale_ref.pixel_distance == 400.0
        assert pytest.approx(scale_ref.meters_per_pixel, 1e-4) == 0.05
        assert scale_ref.calibration_method == "reference_points"

        # Apply to floorplan
        fp = processor.create_synthetic_architectural_floorplan(
            building_id="bldg_test",
            floor_id="fl_01",
            name="Calibrated Floor",
            scale_reference=scale_ref,
        )
        assert fp.is_scale_calibrated is True
        assert fp.physical_width_meters == 50.0
        assert fp.physical_height_meters == 40.0

    def test_point_in_polygon_containing_region(self):
        processor = FloorplanProcessor()
        room1 = SpatialRegion(
            region_id="reg_alpha",
            building_id="bldg_test",
            floor_id="fl_01",
            name="Alpha Wing",
            region_type=SpatialRegionType.ROOM.value,
            polygon=[Point2D(x=0, y=0), Point2D(x=20, y=0), Point2D(x=20, y=20), Point2D(x=0, y=20)],
            center=Point2D(x=10, y=10),
            provenance=MeasurementProvenance.CALIBRATED.value,
        )
        corridor = SpatialRegion(
            region_id="reg_corr",
            building_id="bldg_test",
            floor_id="fl_01",
            name="Main Corridor",
            region_type=SpatialRegionType.CORRIDOR.value,
            polygon=[Point2D(x=20, y=0), Point2D(x=40, y=0), Point2D(x=40, y=20), Point2D(x=20, y=20)],
            center=Point2D(x=30, y=10),
            provenance=MeasurementProvenance.CALIBRATED.value,
        )
        fp = FloorplanModel(
            floorplan_id="fp_test",
            building_id="bldg_test",
            floor_id="fl_01",
            name="Test FP",
            image_width_px=1000,
            image_height_px=800,
            regions=[room1, corridor],
            nodes=[],
            edges=[],
        )

        reg1 = processor.find_containing_region(Point2D(x=5, y=5), fp)
        assert reg1 is not None
        assert reg1.region_id == "reg_alpha"

        reg2 = processor.find_containing_region(Point2D(x=25, y=15), fp)
        assert reg2 is not None
        assert reg2.region_id == "reg_corr"


class TestVideoVisualGeometry:
    """Test video frame feature extraction, motion tracking, and ground-contact geometry."""

    def test_video_feature_extraction(self):
        extractor = VideoGeometryExtractor()
        # Detections in frame 1280x720
        detections = [
            Detection(
                detection_id="det_p1",
                camera_id="CAM_LOBBY_01",
                frame_id="f10",
                frame_number=10,
                timestamp=datetime.now(timezone.utc),
                class_name=DetectionType.PERSON,
                confidence=0.88,
                bbox=BoundingBox(x1=100.0, y1=200.0, x2=180.0, y2=400.0),
            ),
            Detection(
                detection_id="det_f1",
                camera_id="CAM_LOBBY_01",
                frame_id="f10",
                frame_number=10,
                timestamp=datetime.now(timezone.utc),
                class_name=DetectionType.FIRE,
                confidence=0.92,
                bbox=BoundingBox(x1=500.0, y1=300.0, x2=600.0, y2=450.0),
            ),
        ]

        features = extractor.extract_frame_geometry(
            frame_id="frame_0010",
            camera_id="CAM_LOBBY_01",
            detections=detections,
            frame_width=1280,
            frame_height=720,
            timestamp_seconds=1.0,
        )

        assert len(features) == 2
        # Ground contact for person is bottom-center: x = (100+180)/2 = 140, y = 400
        person_feat = next(f for f in features if f.detected_class == DetectionType.PERSON.value)
        assert person_feat.ground_contact_pixel.x == 140.0
        assert person_feat.ground_contact_pixel.y == 400.0
        assert person_feat.hazard_pixel_area == 80.0 * 200.0
        assert person_feat.provenance == MeasurementProvenance.MEASURED.value

    def test_perspective_vanishing_point_estimation(self):
        extractor = VideoGeometryExtractor()
        # Two converging lines representing hallway edges
        line_left = (Point2D(x=100.0, y=700.0), Point2D(x=400.0, y=400.0))
        line_right = (Point2D(x=900.0, y=700.0), Point2D(x=600.0, y=400.0))

        vp = extractor.estimate_perspective_vanishing_point([line_left, line_right])
        assert vp is not None
        assert pytest.approx(vp.x, 1e-1) == 500.0
        assert pytest.approx(vp.y, 1e-1) == 300.0


class TestMultiCameraSpatialFusion:
    """Test spatial deduplication, clustering, and multi-floor isolation."""

    def test_duplicate_hazard_spatial_clustering(self):
        fusion = MultiCameraSpatialFusionEngine(fusion_spatial_threshold_meters=3.5)

        # Two cameras observe the same fire from different angles on Floor 1
        # CAM1 sees fire at (20.0, 15.0), CAM2 sees fire at (21.2, 16.0) -> dist ~ 1.56m <= 3.5m
        det1 = Detection(
            detection_id="det_1",
            camera_id="CAM_WEST_01",
            frame_id="f1",
            frame_number=1,
            timestamp=datetime.now(timezone.utc),
            class_name=DetectionType.FIRE,
            confidence=0.85,
            bbox=BoundingBox(x1=0, y1=0, x2=10, y2=10),
            floor_point=Point2D(x=20.0, y=15.0),
        )
        det2 = Detection(
            detection_id="det_2",
            camera_id="CAM_WEST_02",
            frame_id="f1",
            frame_number=1,
            timestamp=datetime.now(timezone.utc),
            class_name=DetectionType.FIRE,
            confidence=0.92,
            bbox=BoundingBox(x1=0, y1=0, x2=10, y2=10),
            floor_point=Point2D(x=21.2, y=16.0),
        )

        camera_detections = [
            ("CAM_WEST_01", [det1], None),
            ("CAM_WEST_02", [det2], None),
        ]

        fused_hazards = fusion.fuse_camera_detections(
            building_id="bldg_hq",
            floor_id="fl_01",
            camera_detections=camera_detections,
        )

        # Must merge into single fused hazard cluster
        assert len(fused_hazards) == 1
        fused = fused_hazards[0]
        assert fused.hazard_type == DetectionType.FIRE.value
        assert pytest.approx(fused.confidence, 1e-2) == 0.92  # Max confidence
        assert "CAM_WEST_01" in fused.fused_from_cameras
        assert "CAM_WEST_02" in fused.fused_from_cameras
        assert fused.provenance == MeasurementProvenance.CALIBRATED.value
        # Centroid should be between 20.0 and 21.2
        assert 20.0 <= fused.floor_point.x <= 21.2
        assert 15.0 <= fused.floor_point.y <= 16.0

    def test_distinct_hazards_preserved_without_collision(self):
        fusion = MultiCameraSpatialFusionEngine(fusion_spatial_threshold_meters=3.5)

        # Hazard in West Wing (10, 10) vs Hazard in East Wing (45, 30) -> dist >> 3.5m
        det_west = Detection(
            detection_id="det_w",
            camera_id="CAM_WEST_01",
            frame_id="f1",
            frame_number=1,
            timestamp=datetime.now(timezone.utc),
            class_name=DetectionType.FIRE,
            confidence=0.80,
            bbox=BoundingBox(x1=0, y1=0, x2=10, y2=10),
            floor_point=Point2D(x=10.0, y=10.0),
        )
        det_east = Detection(
            detection_id="det_e",
            camera_id="CAM_EAST_01",
            frame_id="f1",
            frame_number=1,
            timestamp=datetime.now(timezone.utc),
            class_name=DetectionType.SMOKE,
            confidence=0.75,
            bbox=BoundingBox(x1=0, y1=0, x2=10, y2=10),
            floor_point=Point2D(x=45.0, y=30.0),
        )

        fused = fusion.fuse_camera_detections(
            building_id="bldg_hq",
            floor_id="fl_01",
            camera_detections=[("CAM_WEST_01", [det_west], None), ("CAM_EAST_01", [det_east], None)],
        )

        # Both hazards preserved distinctly
        assert len(fused) == 2
        types = {h.hazard_type for h in fused}
        assert DetectionType.FIRE.value in types
        assert DetectionType.SMOKE.value in types


class TestDynamicRoutingOnCustomTopology:
    """Test dynamic route computation over arbitrary configured/extracted graphs."""

    def test_routing_on_arbitrary_floorplan_graph(self):
        routing_engine = MultiFactorRoutingEngine()
        risk_engine = DeterministicRiskEngine()

        # Dynamic graph with 3 rooms and 2 exits
        # Room A -> Corridor 1 -> Exit 1
        # Room A -> Corridor 2 -> Exit 2
        nodes = [
            NavigationNode(node_id="room_A", building_id="bldg_dyn", floor_id="fl_01", label="Room A", x=5.0, y=5.0, is_exit=False),
            NavigationNode(node_id="corr_1", building_id="bldg_dyn", floor_id="fl_01", label="North Hall", x=15.0, y=2.0, is_exit=False),
            NavigationNode(node_id="corr_2", building_id="bldg_dyn", floor_id="fl_01", label="South Hall", x=15.0, y=8.0, is_exit=False),
            NavigationNode(node_id="exit_1", building_id="bldg_dyn", floor_id="fl_01", label="North Exit", x=25.0, y=2.0, is_exit=True),
            NavigationNode(node_id="exit_2", building_id="bldg_dyn", floor_id="fl_01", label="South Exit", x=25.0, y=8.0, is_exit=True),
        ]

        edges = [
            NavigationEdge(edge_id="e_a_c1", building_id="bldg_dyn", floor_id="fl_01", from_node="room_A", to_node="corr_1", length_meters=10.0),
            NavigationEdge(edge_id="e_c1_x1", building_id="bldg_dyn", floor_id="fl_01", from_node="corr_1", to_node="exit_1", length_meters=10.0),
            NavigationEdge(edge_id="e_a_c2", building_id="bldg_dyn", floor_id="fl_01", from_node="room_A", to_node="corr_2", length_meters=10.0),
            NavigationEdge(edge_id="e_c2_x2", building_id="bldg_dyn", floor_id="fl_01", from_node="corr_2", to_node="exit_2", length_meters=10.0),
        ]

        # Case 1: No hazards -> routes to closest exit
        route = routing_engine.compute_route(
            nodes=nodes,
            edges=edges,
            origin_node_id="room_A",
            destination_exit_ids=["exit_1", "exit_2"],
        )
        assert route.status == RouteStatus.VALID
        assert route.origin_node == "room_A"
        assert route.destination_node in ["exit_1", "exit_2"]

        # Case 2: Fire at North Hall (corr_1) -> dynamic routing reroutes to South Exit (exit_2)
        detections = [
            Detection(
                detection_id="det_fire_c1",
                camera_id="CAM_NORTH_01",
                frame_id="f1",
                frame_number=1,
                timestamp=datetime.now(timezone.utc),
                class_name=DetectionType.FIRE,
                confidence=0.95,
                bbox=BoundingBox(x1=0, y1=0, x2=10, y2=10),
                floor_point=Point2D(x=15.0, y=2.0),  # Exact point of corr_1
            )
        ]
        risk_snapshot = risk_engine.calculate_risk(
            building_id="bldg_dyn",
            floor_id="fl_01",
            nodes=nodes,
            detections=detections,
            smoke_observations=[],
        )

        assert risk_snapshot.node_risks["corr_1"] > 0.4

        safe_route = routing_engine.compute_route(
            nodes=nodes,
            edges=edges,
            origin_node_id="room_A",
            destination_exit_ids=["exit_1", "exit_2"],
            risk_snapshot=risk_snapshot,
        )

        # Route must divert to South Hall and South Exit
        assert safe_route.destination_node == "exit_2"
        assert "corr_1" not in safe_route.path_nodes
        assert "corr_2" in safe_route.path_nodes


