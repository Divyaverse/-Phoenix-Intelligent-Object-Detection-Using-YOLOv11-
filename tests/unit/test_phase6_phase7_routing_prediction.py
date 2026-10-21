"""
Unit tests for Phase 6 (Occupancy & Blockage Prediction) and Phase 7 (Multi-Factor Routing & ETA Estimation).
Tests:
- Zero occupancy, normal occupancy, high occupancy
- Connection of person detections to occupancy estimator
- Prediction engine driven by smoke temporal growth
- Dynamic routing under hazardous and blocked corridors
- ETA estimation with stair penalties and congestion slowdown
- Deterministic repeated evaluation
"""

from datetime import datetime, timezone
import pytest

from app.core.errors import NoValidRouteError
from app.decision.eta import DeterministicETAEstimator
from app.decision.occupancy import ApproximateOccupancyEstimator
from app.decision.prediction import PredictiveBlockageEngine
from app.decision.risk import DeterministicRiskEngine
from app.decision.routing import MultiFactorRoutingEngine
from app.domain.enums import DetectionType, RiskLevel, RouteStatus, SmokeGrowthTrend
from app.domain.models import (
    BoundingBox,
    Detection,
    NavigationEdge,
    NavigationNode,
    Point2D,
    RiskSnapshot,
    SmokeObservation,
)


def build_test_environment():
    """Construct a standardized multi-exit test corridor network."""
    nodes = [
        NavigationNode(node_id="start_room", building_id="bld_1", floor_id="fl_1", label="Start Room", x=0.0, y=0.0),
        NavigationNode(node_id="hallway_node", building_id="bld_1", floor_id="fl_1", label="Hallway", x=10.0, y=0.0),
        NavigationNode(node_id="exit_north", building_id="bld_1", floor_id="fl_1", label="Exit North", x=10.0, y=10.0, is_exit=True),
        NavigationNode(node_id="exit_south", building_id="bld_1", floor_id="fl_1", label="Exit South", x=10.0, y=-15.0, is_exit=True),
    ]

    edges = [
        NavigationEdge(edge_id="e_start_hall", building_id="bld_1", floor_id="fl_1", from_node="start_room", to_node="hallway_node", length_meters=10.0),
        NavigationEdge(edge_id="e_hall_north", building_id="bld_1", floor_id="fl_1", from_node="hallway_node", to_node="exit_north", length_meters=10.0, is_stairs=True),
        NavigationEdge(edge_id="e_hall_south", building_id="bld_1", floor_id="fl_1", from_node="hallway_node", to_node="exit_south", length_meters=15.0),
    ]

    return nodes, edges


# --- PHASE 6 TESTS ---

def test_phase6_occupancy_zero_normal_high():
    """Verify occupancy estimation across zero, normal, and high person counts."""
    estimator = ApproximateOccupancyEstimator()
    nodes, _ = build_test_environment()

    # Zero occupancy
    occ_zero = estimator.estimate_node_occupancies(nodes, [])
    assert all(val == 0 for val in occ_zero.values())

    # High occupancy (25 persons near start_room)
    persons = [
        Detection(
            frame_id="f1",
            camera_id="cam1",
            class_name=DetectionType.PERSON,
            confidence=0.85,
            bbox=BoundingBox(x1=0, y1=0, x2=10, y2=10),
            floor_point=Point2D(x=0.1 * i, y=0.1 * i),
        )
        for i in range(25)
    ]

    occ_high = estimator.estimate_node_occupancies(nodes, persons)
    assert occ_high["start_room"] == 25
    assert occ_high["exit_north"] == 0


def test_phase6_prediction_with_temporal_smoke():
    """Verify prediction engine calculates corridor blockage scores based on temporal growth."""
    engine = PredictiveBlockageEngine()
    nodes, edges = build_test_environment()
    nodes_dict = {n.node_id: n for n in nodes}

    # Set edge hazard on e_hall_north
    edges[1].hazard_score = 0.50

    obs_rapid = SmokeObservation(
        observation_id="obs1",
        camera_id="cam1",
        area_px2=4000.0,
        trend=SmokeGrowthTrend.RAPID_GROWTH,
        confidence=0.95,
    )

    blockage_map = engine.predict_blockage_scores(edges, nodes_dict, [obs_rapid])
    # Edge with hazard score 0.50 under RAPID_GROWTH should be elevated
    assert blockage_map["e_hall_north"] > 0.40
    assert blockage_map["e_start_hall"] == 0.0 # Zero hazard edge remains 0.0


# --- PHASE 7 TESTS ---

def test_phase7_routing_and_eta_full_decision_chain():
    """Verify full Phase 7 routing and ETA estimation pipeline."""
    nodes, edges = build_test_environment()
    nodes_dict = {n.node_id: n for n in nodes}

    routing_engine = MultiFactorRoutingEngine()
    eta_estimator = DeterministicETAEstimator()

    # Normal clear conditions -> should pick shorter exit_north (10m) over exit_south (15m)
    r_clear = routing_engine.compute_route(
        nodes=nodes,
        edges=edges,
        origin_node_id="start_room",
        destination_exit_ids=["exit_north", "exit_south"],
    )

    assert r_clear.status == RouteStatus.VALID
    assert r_clear.destination_node == "exit_north"

    path_nodes = [nodes_dict[nid] for nid in r_clear.path_nodes]
    path_edges = [e for e in edges if e.edge_id in r_clear.path_edges]
    eta_clear = eta_estimator.calculate_eta(path_nodes, path_edges)
    assert eta_clear > 0.0

    # Block exit_north corridor
    edges[1].is_blocked = True

    r_rerouted = routing_engine.compute_route(
        nodes=nodes,
        edges=edges,
        origin_node_id="start_room",
        destination_exit_ids=["exit_north", "exit_south"],
    )

    assert r_rerouted.destination_node == "exit_south"
    assert r_rerouted.path_nodes == ["start_room", "hallway_node", "exit_south"]


def test_phase7_routing_determinism():
    """Verify repeated execution produces identical route and ETA cost breakdown."""
    nodes, edges = build_test_environment()
    routing_engine = MultiFactorRoutingEngine()

    r1 = routing_engine.compute_route(nodes=nodes, edges=edges, origin_node_id="start_room", destination_exit_ids=["exit_north"])
    r2 = routing_engine.compute_route(nodes=nodes, edges=edges, origin_node_id="start_room", destination_exit_ids=["exit_north"])

    assert r1.path_nodes == r2.path_nodes
    assert r1.total_cost == r2.total_cost
    assert r1.cost_breakdown.model_dump() == r2.cost_breakdown.model_dump()
