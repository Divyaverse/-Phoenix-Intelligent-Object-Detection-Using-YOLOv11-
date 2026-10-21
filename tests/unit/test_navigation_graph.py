"""
Unit tests for NetworkX navigation graph representation.
"""

from app.domain.models import NavigationEdge, NavigationNode
from app.graph.navigation_graph import NavigationGraph


def test_navigation_graph_construction_and_nearest_node():
    """Verify graph creation, node lookup, and nearest node spatial query."""
    nodes = [
        NavigationNode(node_id="n_room", building_id="bld_1", floor_id="fl_1", label="Room 101", x=2.0, y=2.0),
        NavigationNode(node_id="n_hall", building_id="bld_1", floor_id="fl_1", label="Hallway", x=10.0, y=2.0),
        NavigationNode(node_id="n_exit", building_id="bld_1", floor_id="fl_1", label="Exit North", x=20.0, y=2.0, is_exit=True),
    ]
    edges = [
        NavigationEdge(edge_id="e1", building_id="bld_1", floor_id="fl_1", from_node="n_room", to_node="n_hall", length_meters=8.0),
        NavigationEdge(edge_id="e2", building_id="bld_1", floor_id="fl_1", from_node="n_hall", to_node="n_exit", length_meters=10.0),
    ]

    graph = NavigationGraph.from_nodes_and_edges("bld_1", "fl_1", nodes, edges)

    assert len(graph.get_all_nodes()) == 3
    assert len(graph.get_all_edges()) == 2
    assert graph.get_exit_node_ids() == ["n_exit"]
    assert graph.is_connected() is True

    # Spatial query: point (2.1, 2.2) should resolve to n_room
    nearest = graph.find_nearest_node(x=2.1, y=2.2)
    assert nearest == "n_room"

    # Spatial query: point (18.0, 2.0) should resolve to n_exit
    nearest_exit = graph.find_nearest_node(x=18.0, y=2.0)
    assert nearest_exit == "n_exit"
