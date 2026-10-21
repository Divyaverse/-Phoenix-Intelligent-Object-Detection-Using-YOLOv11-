"""
Predictive corridor blockage engine for PHOENIX.
"""

from typing import Optional
import numpy as np

from app.core.config import PredictionConfig, settings
from app.domain.enums import SmokeGrowthTrend
from app.domain.interfaces import PredictionEngine
from app.domain.models import NavigationEdge, NavigationNode, SmokeObservation


class PredictiveBlockageEngine(PredictionEngine):
    """
    Computes forecasted corridor blockage scores for navigation edges
    based on observed temporal smoke growth rates and spatial proximity.
    """

    def __init__(self, config: Optional[PredictionConfig] = None) -> None:
        self.config = config or settings.prediction

    def predict_blockage_scores(
        self,
        edges: list[NavigationEdge],
        nodes_dict: dict[str, NavigationNode],
        smoke_observations: list[SmokeObservation],
    ) -> dict[str, float]:
        """
        Compute predicted blockage scores in [0.0, 1.0] for each edge.
        """
        blockage_map: dict[str, float] = {e.edge_id: 0.0 for e in edges}

        if not smoke_observations or not edges:
            return blockage_map

        # Evaluate maximum temporal growth intensity across observed smoke regions
        max_growth_signal = 0.0
        for obs in smoke_observations:
            if obs.trend == SmokeGrowthTrend.RAPID_GROWTH:
                intensity = 1.0
            elif obs.trend == SmokeGrowthTrend.MODERATE_GROWTH:
                intensity = 0.6
            elif obs.trend == SmokeGrowthTrend.STABLE:
                intensity = 0.2
            else:
                intensity = 0.0

            # Scale by confidence
            signal = intensity * obs.confidence
            if signal > max_growth_signal:
                max_growth_signal = signal

        w_growth = self.config.growth_extrapolation_weight
        w_hazard = self.config.proximity_hazard_weight

        for edge in edges:
            u_node = nodes_dict.get(edge.from_node)
            v_node = nodes_dict.get(edge.to_node)
            if not u_node or not v_node:
                continue

            # Base hazard score on edge
            current_hz = edge.hazard_score

            # Predictive blockage combines current hazard and projected temporal growth
            projected_blockage = (w_hazard * current_hz) + (w_growth * max_growth_signal * current_hz)

            # If edge already blocked, blockage is 1.0
            if edge.is_blocked:
                projected_blockage = 1.0

            blockage_map[edge.edge_id] = round(float(np.clip(projected_blockage, 0.0, 1.0)), 3)

        return blockage_map
