"""
Unit tests for PHOENIX domain models, enums, and data integrity.
"""

import pytest
from app.domain.enums import (
    CameraStatus,
    DetectionType,
    IncidentSeverity,
    IncidentStatus,
    RiskLevel,
    RouteStatus,
    SmokeGrowthTrend,
    UserRole,
)
from app.domain.models import (
    BoundingBox,
    Building,
    Calibration,
    CalibrationPoint,
    Camera,
    Detection,
    Floor,
    Incident,
    NavigationEdge,
    NavigationNode,
    Point2D,
    RiskSnapshot,
    RouteCostReason,
    RouteRecommendation,
    SmokeObservation,
    User,
)


def test_bounding_box_calculations():
    """Verify BoundingBox geometry properties: width, height, area, center, ground point."""
    bbox = BoundingBox(x1=10.0, y1=20.0, x2=50.0, y2=100.0)
    assert bbox.width == 40.0
    assert bbox.height == 80.0
    assert bbox.area == 3200.0
    assert bbox.center.x == 30.0
    assert bbox.center.y == 60.0
    assert bbox.ground_point.x == 30.0
    assert bbox.ground_point.y == 100.0


def test_detection_model_instantiation(sample_detections):
    """Verify structured Detection model creation with Point2D and BoundingBox."""
    assert len(sample_detections) == 2
    smoke_det = sample_detections[0]
    assert smoke_det.class_name == DetectionType.SMOKE
    assert smoke_det.confidence == 0.88
    assert smoke_det.bbox.width == 100.0
    assert smoke_det.floor_point.x == 2.5


def test_smoke_observation_model():
    """Verify SmokeObservation fields for temporal tracking."""
    obs = SmokeObservation(
        observation_id="obs_001",
        camera_id="cam_001",
        area_px2=1500.0,
        delta_area_px2=300.0,
        dt_seconds=2.0,
        growth_rate_px2_per_sec=150.0,
        smoothed_growth_rate=140.0,
        trend=SmokeGrowthTrend.MODERATE_GROWTH,
        confidence=0.85,
    )
    assert obs.area_px2 == 1500.0
    assert obs.growth_rate_px2_per_sec == 150.0
    assert obs.trend == SmokeGrowthTrend.MODERATE_GROWTH


def test_route_recommendation_and_cost_reason():
    """Verify RouteRecommendation decomposes cost components cleanly."""
    cost = RouteCostReason(
        distance_cost=0.25,
        hazard_cost=0.15,
        occupancy_cost=0.05,
        predicted_blockage_cost=0.10,
        total_cost=0.55,
    )
    rec = RouteRecommendation(
        route_id="route_001",
        building_id="bld_test",
        floor_id="fl_01",
        origin_node="node_room_101",
        destination_node="node_exit_north",
        path_nodes=["node_room_101", "node_corridor_1", "node_exit_north"],
        path_edges=["edge_1", "edge_2"],
        status=RouteStatus.VALID,
        eta_seconds=45.0,
        total_cost=0.55,
        cost_breakdown=cost,
    )
    assert rec.status == RouteStatus.VALID
    assert rec.cost_breakdown.total_cost == 0.55
    assert len(rec.path_nodes) == 3


def test_incident_lifecycle():
    """Verify Incident model supports status progression and affected nodes."""
    incident = Incident(
        incident_id="inc_001",
        organization_id="org_test",
        building_id="bld_test",
        floor_id="fl_01",
        status=IncidentStatus.REPORTED,
        severity=IncidentSeverity.HIGH,
        title="Fire alarm triggered in Corridor B",
        hazard_origin_node="node_corridor_2",
        affected_nodes=["node_corridor_2", "node_room_104"],
    )
    assert incident.status == IncidentStatus.REPORTED
    assert incident.severity == IncidentSeverity.HIGH
    assert "node_corridor_2" in incident.affected_nodes
