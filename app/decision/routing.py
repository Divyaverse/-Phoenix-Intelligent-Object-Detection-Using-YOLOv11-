"""
Deterministic Graph-Based Evacuation Routing Engine using NetworkX.
"""

from datetime import datetime, timezone
from typing import Any, Optional
import networkx as nx
import numpy as np
import uuid

from app.core.config import RoutingConfig, settings
from app.core.errors import NoValidExitError, NoValidRouteError
from app.domain.enums import RouteStatus
from app.domain.interfaces import RoutingEngine
from app.domain.models import (
    NavigationEdge,
    NavigationNode,
    RiskSnapshot,
    RouteCostReason,
    RouteRecommendation,
)


class MultiFactorRoutingEngine(RoutingEngine):
    """
    Deterministic evacuation route optimization engine.
    Calculates least-cost paths across distance, hazard, occupancy, and predicted corridor blockage.
    """

    def __init__(self, config: Optional[RoutingConfig] = None) -> None:
        self.config = config or settings.routing

    def compute_evacuation_route(
        self,
        graph: Any,
        origin_node: str,
        destination_exits: Optional[list[str]] = None,
        risk_snapshot: Optional[RiskSnapshot] = None,
        occupancy_map: Optional[dict[str, int]] = None,
        blockage_predictions: Optional[dict[str, float]] = None,
    ) -> RouteRecommendation:
        """
        Convenience method to compute evacuation route given a NavigationGraph instance.
        """
        if hasattr(graph, "_nodes_dict"):
            nodes = list(graph._nodes_dict.values())
        elif hasattr(graph, "nodes"):
            nodes = list(graph.nodes.values()) if isinstance(graph.nodes, dict) else list(graph.nodes)
        else:
            nodes = []

        if hasattr(graph, "_edges_dict"):
            edges = list(graph._edges_dict.values())
        elif hasattr(graph, "edges"):
            edges = list(graph.edges.values()) if isinstance(graph.edges, dict) else list(graph.edges)
        else:
            edges = []

        exits = destination_exits or [n.node_id for n in nodes if getattr(n, "is_exit", False)]
        return self.compute_route(
            nodes=nodes,
            edges=edges,
            origin_node_id=origin_node,
            destination_exit_ids=exits,
            risk_snapshot=risk_snapshot,
            occupancy_map=occupancy_map,
            blockage_predictions=blockage_predictions,
        )


    def compute_route(
        self,
        nodes: list[NavigationNode],
        edges: list[NavigationEdge],
        origin_node_id: str,
        destination_exit_ids: list[str],
        risk_snapshot: Optional[RiskSnapshot] = None,
        occupancy_map: Optional[dict[str, int]] = None,
        blockage_predictions: Optional[dict[str, float]] = None,
    ) -> RouteRecommendation:
        """
        Compute optimal deterministic evacuation path from origin to closest accessible exit.
        """

        if not nodes:
            raise NoValidRouteError("Cannot route on empty navigation graph (no nodes provided)")

        nodes_dict = {n.node_id: n for n in nodes}
        if origin_node_id not in nodes_dict:
            raise NoValidRouteError(f"Origin node '{origin_node_id}' not found in navigation graph")

        if not destination_exit_ids:
            raise NoValidExitError("No building exits designated for evacuation routing")

        # Validate that designated exit node IDs actually exist
        valid_exit_ids = [eid for eid in destination_exit_ids if eid in nodes_dict]
        if not valid_exit_ids:
            raise NoValidExitError("None of the designated exit node IDs exist in the navigation graph")

        # If origin is already an exit node
        if origin_node_id in valid_exit_ids:
            zero_cost = RouteCostReason(
                distance_cost=0.0,
                hazard_cost=0.0,
                occupancy_cost=0.0,
                predicted_blockage_cost=0.0,
                total_cost=0.0,
            )
            return RouteRecommendation(
                route_id=f"route_{uuid.uuid4().hex[:8]}",
                building_id=nodes_dict[origin_node_id].building_id,
                floor_id=nodes_dict[origin_node_id].floor_id,
                origin_node=origin_node_id,
                destination_node=origin_node_id,
                path_nodes=[origin_node_id],
                path_edges=[],
                status=RouteStatus.VALID,
                eta_seconds=0.0,
                total_cost=0.0,
                cost_breakdown=zero_cost,
                algorithm_version="dijkstra_v1",
            )

        # Build weighted NetworkX graph
        G = nx.Graph()
        for n in nodes:
            G.add_node(n.node_id)

        w = self.config.weights
        w_d = w.get("distance_weight", 0.35)
        w_h = w.get("hazard_weight", 0.40)
        w_o = w.get("occupancy_weight", 0.10)
        w_p = w.get("predicted_blockage_weight", 0.15)
        hard_block_thresh = self.config.hard_block_hazard_threshold

        edge_cost_components: dict[tuple[str, str], RouteCostReason] = {}
        edge_id_lookup: dict[tuple[str, str], str] = {}

        for edge in edges:
            u, v = edge.from_node, edge.to_node
            edge_id_lookup[(u, v)] = edge.edge_id
            edge_id_lookup[(v, u)] = edge.edge_id

            # Node hazards from risk snapshot if available
            node_h = 0.0
            if risk_snapshot and risk_snapshot.node_risks:
                node_h = max(risk_snapshot.node_risks.get(u, 0.0), risk_snapshot.node_risks.get(v, 0.0))

            hazard_val = max(edge.hazard_score, node_h)
            occupancy_val = edge.occupancy_count
            if occupancy_map:
                occupancy_val = max(occupancy_val, occupancy_map.get(u, 0), occupancy_map.get(v, 0))

            pred_val = edge.predicted_blockage_score
            if blockage_predictions:
                pred_val = max(pred_val, blockage_predictions.get(edge.edge_id, 0.0))

            # Check if edge is completely blocked
            if edge.is_blocked or hazard_val >= hard_block_thresh:
                # Do not add passable edge to graph
                continue

            # Normalized components
            norm_dist = max(0.01, edge.length_meters / 50.0) # Scale roughly by 50m corridor length
            norm_hazard = float(np.clip(hazard_val, 0.0, 1.0))
            norm_occ = float(np.clip(occupancy_val / 20.0, 0.0, 1.0)) # Scale by nominal capacity
            norm_pred = float(np.clip(pred_val, 0.0, 1.0))

            c_d = w_d * norm_dist
            c_h = w_h * norm_hazard
            c_o = w_o * norm_occ
            c_p = w_p * norm_pred
            total_edge_weight = max(0.001, c_d + c_h + c_o + c_p)

            reason = RouteCostReason(
                distance_cost=round(c_d, 4),
                hazard_cost=round(c_h, 4),
                occupancy_cost=round(c_o, 4),
                predicted_blockage_cost=round(c_p, 4),
                total_cost=round(total_edge_weight, 4),
            )
            edge_cost_components[(u, v)] = reason
            edge_cost_components[(v, u)] = reason

            G.add_edge(u, v, weight=total_edge_weight, length=edge.length_meters, edge_id=edge.edge_id)

        # Search for shortest path across all valid exits
        best_path: Optional[list[str]] = None
        best_exit: Optional[str] = None
        lowest_total_weight = float("inf")

        for exit_id in valid_exit_ids:
            if not G.has_node(exit_id):
                continue
            try:
                path = nx.shortest_path(G, source=origin_node_id, target=exit_id, weight="weight")
                total_weight = nx.shortest_path_length(G, source=origin_node_id, target=exit_id, weight="weight")
                if total_weight < lowest_total_weight:
                    lowest_total_weight = total_weight
                    best_path = path
                    best_exit = exit_id
            except (nx.NetworkXNoPath, nx.NodeNotFound):
                continue

        if best_path is None or best_exit is None:
            # Explicit fail-closed state
            raise NoValidRouteError(
                f"No accessible evacuation path from '{origin_node_id}' to any building exit",
                details={
                    "origin": origin_node_id,
                    "exits": valid_exit_ids,
                    "status": RouteStatus.NO_VALID_ROUTE.value,
                },
            )

        # Reconstruct path edges and aggregate decomposed cost reasons
        path_edges: list[str] = []
        tot_d, tot_h, tot_o, tot_p = 0.0, 0.0, 0.0, 0.0

        for i in range(len(best_path) - 1):
            u = best_path[i]
            v = best_path[i + 1]
            e_id = edge_id_lookup.get((u, v), f"edge_{u}_{v}")
            path_edges.append(e_id)

            comp = edge_cost_components.get((u, v))
            if comp:
                tot_d += comp.distance_cost
                tot_h += comp.hazard_cost
                tot_o += comp.occupancy_cost
                tot_p += comp.predicted_blockage_cost

        aggregate_cost = RouteCostReason(
            distance_cost=round(tot_d, 4),
            hazard_cost=round(tot_h, 4),
            occupancy_cost=round(tot_o, 4),
            predicted_blockage_cost=round(tot_p, 4),
            total_cost=round(tot_d + tot_h + tot_o + tot_p, 4),
        )

        return RouteRecommendation(
            route_id=f"route_{uuid.uuid4().hex[:8]}",
            building_id=nodes_dict[origin_node_id].building_id,
            floor_id=nodes_dict[origin_node_id].floor_id,
            origin_node=origin_node_id,
            destination_node=best_exit,
            path_nodes=best_path,
            path_edges=path_edges,
            status=RouteStatus.VALID,
            eta_seconds=0.0, # Populated by ETA estimator
            total_cost=aggregate_cost.total_cost,
            cost_breakdown=aggregate_cost,
            algorithm_version=f"{self.config.algorithm}_v1",
            is_degraded=False,
            computed_at=datetime.now(timezone.utc),
        )


# Backward-compatible alias
DeterministicRoutingEngine = MultiFactorRoutingEngine

