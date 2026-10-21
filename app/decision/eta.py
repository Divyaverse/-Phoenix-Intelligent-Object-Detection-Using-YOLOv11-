"""
Deterministic Evacuation Travel Time (ETA) Estimator for PHOENIX.
"""

from typing import Optional
import numpy as np

from app.core.config import ETAConfig, settings
from app.domain.interfaces import ETAEstimator
from app.domain.models import NavigationEdge, NavigationNode, RiskSnapshot


class DeterministicETAEstimator(ETAEstimator):
    """
    Computes estimated evacuation travel times based on route length,
    stairway penalties, congestion slowdown, and hazard visibility reduction.
    """

    def __init__(self, config: Optional[ETAConfig] = None) -> None:
        self.config = config or settings.eta

    def calculate_eta(
        self,
        path_nodes: list[NavigationNode],
        path_edges: list[NavigationEdge],
        occupancy_map: Optional[dict[str, int]] = None,
        risk_snapshot: Optional[RiskSnapshot] = None,
    ) -> float:
        """
        Calculate estimated evacuation time in seconds.
        """
        if not path_edges or len(path_nodes) <= 1:
            return 0.0

        base_speed = max(0.2, self.config.base_walking_speed_mps) # Nominal walking velocity in m/s
        total_time_seconds = 0.0

        for edge in path_edges:
            effective_speed = base_speed

            # 1. Stairs traversal penalty
            if edge.is_stairs:
                effective_speed *= self.config.stairs_speed_factor

            # 2. Occupancy congestion slowdown
            edge_occ = edge.occupancy_count
            if occupancy_map:
                edge_occ = max(
                    edge_occ,
                    occupancy_map.get(edge.from_node, 0),
                    occupancy_map.get(edge.to_node, 0),
                )
            if edge_occ > 5:
                # Scaled congestion penalty between [0.0, congestion_slowdown_max_factor]
                congestion_ratio = min(1.0, (edge_occ - 5) / 20.0)
                slowdown = 1.0 - (self.config.congestion_slowdown_max_factor * congestion_ratio)
                effective_speed *= max(0.3, slowdown)

            # 3. Smoke / hazard visibility reduction
            edge_hz = edge.hazard_score
            if risk_snapshot and risk_snapshot.node_risks:
                edge_hz = max(
                    edge_hz,
                    risk_snapshot.node_risks.get(edge.from_node, 0.0),
                    risk_snapshot.node_risks.get(edge.to_node, 0.0),
                )
            if edge_hz > 0.2:
                effective_speed *= self.config.smoke_visibility_slowdown_factor

            effective_speed = max(0.2, effective_speed)
            edge_time = edge.length_meters / effective_speed
            total_time_seconds += edge_time

        return round(float(total_time_seconds), 1)
