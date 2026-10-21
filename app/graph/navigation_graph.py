"""
Topological Navigation Graph implementation using NetworkX.
"""

from typing import Any, Optional
import networkx as nx
import numpy as np

from app.core.errors import GraphDisconnectedError
from app.domain.models import NavigationEdge, NavigationNode, Point2D


class NavigationGraph:
    """
    Manages the topological navigation network of rooms, corridors, stairwells, and exits.
    Backed by NetworkX graph data structures.
    """

    def __init__(self, building_id: str, floor_id: str) -> None:
        self.building_id = building_id
        self.floor_id = floor_id
        self._graph = nx.Graph()
        self._nodes_dict: dict[str, NavigationNode] = {}
        self._edges_dict: dict[str, NavigationEdge] = {}

    @property
    def raw_graph(self) -> nx.Graph:
        """Underlying NetworkX graph instance."""
        return self._graph

    def add_node(self, node: NavigationNode) -> None:
        """Add a navigation node to the graph."""
        self._nodes_dict[node.node_id] = node
        self._graph.add_node(
            node.node_id,
            label=node.label,
            node_type=node.node_type,
            x=node.x,
            y=node.y,
            is_exit=node.is_exit,
            capacity=node.capacity,
            building_id=node.building_id,
            floor_id=node.floor_id,
        )

    def add_edge(self, edge: NavigationEdge) -> None:
        """Add a navigable edge connection between two nodes."""
        self._edges_dict[edge.edge_id] = edge
        # Ensure endpoints exist
        if edge.from_node not in self._graph or edge.to_node not in self._graph:
            raise KeyError(f"Both edge endpoints must exist in graph: {edge.from_node} -> {edge.to_node}")

        self._graph.add_edge(
            edge.from_node,
            edge.to_node,
            edge_id=edge.edge_id,
            length_meters=edge.length_meters,
            is_stairs=edge.is_stairs,
            is_blocked=edge.is_blocked,
            hazard_score=edge.hazard_score,
            occupancy_count=edge.occupancy_count,
            predicted_blockage_score=edge.predicted_blockage_score,
        )

    def get_node(self, node_id: str) -> Optional[NavigationNode]:
        return self._nodes_dict.get(node_id)

    def get_all_nodes(self) -> list[NavigationNode]:
        return list(self._nodes_dict.values())

    def get_all_edges(self) -> list[NavigationEdge]:
        return list(self._edges_dict.values())

    def get_exit_node_ids(self) -> list[str]:
        """Return all node IDs designated as building/floor exits."""
        return [nid for nid, node in self._nodes_dict.items() if node.is_exit]

    def find_nearest_node(self, x: float, y: float) -> Optional[str]:
        """Find the closest navigation node ID to the given metric (x, y) floorplan coordinate."""
        if not self._nodes_dict:
            return None

        best_id = None
        min_dist_sq = float("inf")

        for nid, node in self._nodes_dict.items():
            dist_sq = (node.x - x) ** 2 + (node.y - y) ** 2
            if dist_sq < min_dist_sq:
                min_dist_sq = dist_sq
                best_id = nid

        return best_id

    def _resolve_edge(self, arg1: str, arg2: Optional[Any] = None) -> tuple[Optional[str], Optional[str]]:
        """Resolve edge endpoints whether passed as (edge_id) or (u, v)."""
        if arg1 in self._edges_dict:
            e = self._edges_dict[arg1]
            return e.from_node, e.to_node
        if arg2 is not None and isinstance(arg2, str) and self._graph.has_edge(arg1, arg2):
            return arg1, arg2
        return None, None

    def update_edge_hazard(self, u_or_edge_id: str, v: Optional[str] = None, hazard_score: Optional[float] = None) -> None:
        """Update active hazard risk score on edge."""
        if hazard_score is None and v is not None and isinstance(v, (int, float)):
            score = float(v)
            u_node, v_node = self._resolve_edge(u_or_edge_id)
        elif hazard_score is not None:
            score = float(hazard_score)
            u_node, v_node = self._resolve_edge(u_or_edge_id, v)
        else:
            return

        if u_node and v_node and self._graph.has_edge(u_node, v_node):
            clamped = float(np.clip(score, 0.0, 1.0))
            self._graph[u_node][v_node]["hazard_score"] = clamped
            if u_or_edge_id in self._edges_dict:
                self._edges_dict[u_or_edge_id].hazard_score = clamped

    def update_edge_occupancy(self, u_or_edge_id: str, v: Optional[str] = None, occupancy_count: Optional[int] = None) -> None:
        """Update current occupancy count on edge."""
        if occupancy_count is None and v is not None and isinstance(v, (int, float)):
            count = int(v)
            u_node, v_node = self._resolve_edge(u_or_edge_id)
        elif occupancy_count is not None:
            count = int(occupancy_count)
            u_node, v_node = self._resolve_edge(u_or_edge_id, v)
        else:
            return

        if u_node and v_node and self._graph.has_edge(u_node, v_node):
            val = max(0, count)
            self._graph[u_node][v_node]["occupancy_count"] = val
            if u_or_edge_id in self._edges_dict:
                self._edges_dict[u_or_edge_id].occupancy_count = val

    def update_edge_prediction(self, u_or_edge_id: str, v: Optional[str] = None, predicted_blockage_score: Optional[float] = None) -> None:
        """Update forecasted blockage score on edge."""
        if predicted_blockage_score is None and v is not None and isinstance(v, (int, float)):
            score = float(v)
            u_node, v_node = self._resolve_edge(u_or_edge_id)
        elif predicted_blockage_score is not None:
            score = float(predicted_blockage_score)
            u_node, v_node = self._resolve_edge(u_or_edge_id, v)
        else:
            return

        if u_node and v_node and self._graph.has_edge(u_node, v_node):
            clamped = float(np.clip(score, 0.0, 1.0))
            self._graph[u_node][v_node]["predicted_blockage_score"] = clamped
            if u_or_edge_id in self._edges_dict:
                self._edges_dict[u_or_edge_id].predicted_blockage_score = clamped

    def update_edge_predicted_blockage(self, u_or_edge_id: str, v: Optional[str] = None, predicted_blockage_score: Optional[float] = None) -> None:
        """Alias for update_edge_prediction."""
        self.update_edge_prediction(u_or_edge_id, v, predicted_blockage_score)

    def set_edge_blocked(self, u_or_edge_id: str, v: Optional[Any] = None, blocked: Optional[bool] = None) -> None:
        """Mark an edge as blocked or passable."""
        if blocked is None and v is not None and isinstance(v, bool):
            is_b = v
            u_node, v_node = self._resolve_edge(u_or_edge_id)
        elif blocked is not None:
            is_b = bool(blocked)
            u_node, v_node = self._resolve_edge(u_or_edge_id, v)
        else:
            return

        if u_node and v_node and self._graph.has_edge(u_node, v_node):
            self._graph[u_node][v_node]["is_blocked"] = is_b
            if u_or_edge_id in self._edges_dict:
                self._edges_dict[u_or_edge_id].is_blocked = is_b

    def is_connected(self) -> bool:
        """Check if all graph nodes are connected."""

        if len(self._graph) <= 1:
            return True
        return nx.is_connected(self._graph)

    @classmethod
    def from_nodes_and_edges(
        cls,
        building_id: str,
        floor_id: str,
        nodes: list[NavigationNode],
        edges: list[NavigationEdge],
    ) -> "NavigationGraph":
        """Factory constructor initializing graph from collections of nodes and edges."""
        graph = cls(building_id=building_id, floor_id=floor_id)
        for n in nodes:
            graph.add_node(n)
        for e in edges:
            graph.add_edge(e)
        return graph
