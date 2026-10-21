"""
Unit tests for deterministic evacuation routing engine.
"""

import pytest

from app.core.errors import NoValidExitError, NoValidRouteError
from app.decision.routing import MultiFactorRoutingEngine
from app.domain.enums import RouteStatus
from app.domain.models import NavigationEdge, NavigationNode, RiskSnapshot


def build_test_floor_network():
    """
    Build a standard test grid:
    (Room 101) --- [Edge 1] --- (Junction) --- [Edge 2] --- (Exit East)
                                    |
                                 [Edge 3]
                                    |
                               (Exit South)
    """
    nodes = [
        NavigationNode(node_id="room_101", building_id="bld_1", floor_id="fl_1", label="Room 101", x=0.0, y=0.0),
        NavigationNode(node_id="junction", building_id="bld_1", floor_id="fl_1", label="Hall Junction", x=10.0, y=0.0),
        NavigationNode(node_id="exit_east", building_id="bld_1", floor_id="fl_1", label="Exit East", x=20.0, y=0.0, is_exit=True),
        NavigationNode(node_id="exit_south", building_id="bld_1", floor_id="fl_1", label="Exit South", x=10.0, y=15.0, is_exit=True),
    ]
    edges = [
        NavigationEdge(edge_id="e1", building_id="bld_1", floor_id="fl_1", from_node="room_101", to_node="junction", length_meters=10.0),
        NavigationEdge(edge_id="e2", building_id="bld_1", floor_id="fl_1", from_node="junction", to_node="exit_east", length_meters=10.0),
        NavigationEdge(edge_id="e3", building_id="bld_1", floor_id="fl_1", from_node="junction", to_node="exit_south", length_meters=15.0),
    ]
    return nodes, edges


def test_routing_normal_clear_path():
    """Verify routing selects shortest exit (Exit East) under clear conditions."""
    engine = MultiFactorRoutingEngine()
    nodes, edges = build_test_floor_network()

    recommendation = engine.compute_route(
        nodes=nodes,
        edges=edges,
        origin_node_id="room_101",
        destination_exit_ids=["exit_east", "exit_south"],
    )

    assert recommendation.status == RouteStatus.VALID
    assert recommendation.destination_node == "exit_east"
    assert recommendation.path_nodes == ["room_101", "junction", "exit_east"]
    assert recommendation.path_edges == ["e1", "e2"]
    assert recommendation.cost_breakdown.total_cost > 0.0
    assert recommendation.cost_breakdown.hazard_cost == 0.0


def test_routing_dynamic_hazard_rerouting():
    """Verify routing dynamic rerouting: when Exit East has high hazard, route switches to Exit South."""
    engine = MultiFactorRoutingEngine()
    nodes, edges = build_test_floor_network()

    # Place high hazard (0.80) on Exit East corridor (e2)
    risk_snapshot = RiskSnapshot(
        snapshot_id="risk_test",
        building_id="bld_1",
        floor_id="fl_1",
        node_risks={"exit_east": 0.85, "junction": 0.10, "room_101": 0.0, "exit_south": 0.0},
    )

    recommendation = engine.compute_route(
        nodes=nodes,
        edges=edges,
        origin_node_id="room_101",
        destination_exit_ids=["exit_east", "exit_south"],
        risk_snapshot=risk_snapshot,
    )

    # Route should intelligently avoid exit_east and take exit_south
    assert recommendation.destination_node == "exit_south"
    assert recommendation.path_nodes == ["room_101", "junction", "exit_south"]


def test_routing_hard_block_failure():
    """Verify NoValidRouteError is raised when all paths to exits are blocked."""
    engine = MultiFactorRoutingEngine()
    nodes, edges = build_test_floor_network()

    # Block both exits
    edges[1].is_blocked = True # e2 blocked
    edges[2].is_blocked = True # e3 blocked

    with pytest.raises(NoValidRouteError, match="No accessible evacuation path"):
        engine.compute_route(
            nodes=nodes,
            edges=edges,
            origin_node_id="room_101",
            destination_exit_ids=["exit_east", "exit_south"],
        )


def test_routing_no_exits_fails():
    """Verify NoValidExitError is raised when no valid exit IDs are specified."""
    engine = MultiFactorRoutingEngine()
    nodes, edges = build_test_floor_network()

    with pytest.raises(NoValidExitError):
        engine.compute_route(
            nodes=nodes,
            edges=edges,
            origin_node_id="room_101",
            destination_exit_ids=[],
        )
