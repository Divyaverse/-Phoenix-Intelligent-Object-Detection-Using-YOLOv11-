"""
Unit tests for deterministic evacuation travel time (ETA) estimation.
"""

from app.decision.eta import DeterministicETAEstimator
from app.domain.models import NavigationEdge, NavigationNode, RiskSnapshot


def test_deterministic_eta_calculation():
    """
    Verify basic ETA calculation:
    Length = 24 meters, Base speed = 1.2 m/s -> Expected ETA = 20.0 seconds.
    """
    estimator = DeterministicETAEstimator()

    nodes = [
        NavigationNode(node_id="n1", building_id="bld_1", floor_id="fl_1", label="N1", x=0.0, y=0.0),
        NavigationNode(node_id="n2", building_id="bld_1", floor_id="fl_1", label="N2", x=24.0, y=0.0),
    ]
    edges = [
        NavigationEdge(edge_id="e1", building_id="bld_1", floor_id="fl_1", from_node="n1", to_node="n2", length_meters=24.0),
    ]

    eta = estimator.calculate_eta(nodes, edges)
    assert abs(eta - 20.0) < 0.1


def test_eta_stairs_slowdown():
    """Verify stair edges apply configured slowdown penalty."""
    estimator = DeterministicETAEstimator()

    nodes = [
        NavigationNode(node_id="n1", building_id="bld_1", floor_id="fl_1", label="N1", x=0.0, y=0.0),
        NavigationNode(node_id="n2", building_id="bld_1", floor_id="fl_1", label="N2", x=12.0, y=0.0),
    ]
    edges_normal = [
        NavigationEdge(edge_id="e1", building_id="bld_1", floor_id="fl_1", from_node="n1", to_node="n2", length_meters=12.0, is_stairs=False),
    ]
    edges_stairs = [
        NavigationEdge(edge_id="e1", building_id="bld_1", floor_id="fl_1", from_node="n1", to_node="n2", length_meters=12.0, is_stairs=True),
    ]

    eta_normal = estimator.calculate_eta(nodes, edges_normal)
    eta_stairs = estimator.calculate_eta(nodes, edges_stairs)

    assert eta_stairs > eta_normal


def test_eta_congestion_slowdown():
    """Verify high occupancy applies congestion slowdown penalty."""
    estimator = DeterministicETAEstimator()

    nodes = [
        NavigationNode(node_id="n1", building_id="bld_1", floor_id="fl_1", label="N1", x=0.0, y=0.0),
        NavigationNode(node_id="n2", building_id="bld_1", floor_id="fl_1", label="N2", x=24.0, y=0.0),
    ]
    edges = [
        NavigationEdge(edge_id="e1", building_id="bld_1", floor_id="fl_1", from_node="n1", to_node="n2", length_meters=24.0),
    ]

    occ_dense = {"n1": 25, "n2": 20}
    eta_congested = estimator.calculate_eta(nodes, edges, occupancy_map=occ_dense)
    eta_clear = estimator.calculate_eta(nodes, edges, occupancy_map={})

    assert eta_congested > eta_clear
