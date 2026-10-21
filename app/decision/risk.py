"""
Deterministic Spatial Risk Engine for PHOENIX.
"""

from datetime import datetime, timezone
from typing import Optional
import numpy as np
import uuid

from app.core.config import RiskConfig, settings
from app.domain.enums import DetectionType, RiskLevel, SmokeGrowthTrend
from app.domain.interfaces import RiskEngine
from app.domain.models import Detection, NavigationNode, Point2D, RiskSnapshot, SmokeObservation


class DeterministicRiskEngine(RiskEngine):
    """
    Computes spatial risk scores for building navigation nodes by fusing
    visual fire/smoke detections, spatial proximity decay, and temporal smoke growth trends.
    """

    def __init__(self, config: Optional[RiskConfig] = None) -> None:
        self.config = config or settings.risk

    def calculate_risk(
        self,
        building_id: str,
        floor_id: str,
        nodes: list[NavigationNode],
        detections: list[Detection],
        smoke_observations: list[SmokeObservation],
    ) -> RiskSnapshot:
        """
        Compute deterministic risk scores for all navigation nodes.
        """
        node_risks: dict[str, float] = {n.node_id: 0.0 for n in nodes}
        active_hazards_count = 0

        # Build list of active hazard centers with mapped floor coordinates
        hazard_sources: list[dict] = []
        for det in detections:
            if det.class_name in (DetectionType.FIRE, DetectionType.SMOKE) and det.floor_point is not None:
                base_weight = self.config.base_hazard_weights.get(det.class_name.value, 0.50)
                hazard_sources.append({
                    "class": det.class_name,
                    "confidence": det.confidence,
                    "point": det.floor_point,
                    "base_weight": base_weight,
                    "camera_id": det.camera_id,
                })

        active_hazards_count = len(hazard_sources)

        # Precompute camera temporal growth multiplier
        camera_growth_mult: dict[str, float] = {}
        for obs in smoke_observations:
            mult = 1.0
            if obs.trend == SmokeGrowthTrend.RAPID_GROWTH:
                mult = self.config.growth_risk_multiplier
            elif obs.trend == SmokeGrowthTrend.MODERATE_GROWTH:
                mult = 1.0 + (self.config.growth_risk_multiplier - 1.0) * 0.5
            camera_growth_mult[obs.camera_id] = mult

        decay_lambda = self.config.proximity_decay_lambda

        # For each node, calculate spatial risk contribution from all hazard sources
        for node in nodes:
            max_node_risk = 0.0
            for hz in hazard_sources:
                hz_point: Point2D = hz["point"]
                dist = np.sqrt((node.x - hz_point.x) ** 2 + (node.y - hz_point.y) ** 2)

                # Spatial exponential proximity decay: exp(-lambda * distance)
                proximity_factor = np.exp(-decay_lambda * dist)

                # Temporal growth factor
                growth_mult = camera_growth_mult.get(hz["camera_id"], 1.0)

                hazard_intensity = hz["base_weight"] * hz["confidence"] * growth_mult * proximity_factor
                if hazard_intensity > max_node_risk:
                    max_node_risk = hazard_intensity

            node_risks[node.node_id] = round(float(np.clip(max_node_risk, 0.0, 1.0)), 3)

        # Determine global floor risk level based on configured level thresholds
        highest_risk = max(node_risks.values()) if node_risks else 0.0
        global_level = self._classify_global_risk(highest_risk)

        return RiskSnapshot(
            snapshot_id=f"risk_{uuid.uuid4().hex[:8]}",
            building_id=building_id,
            floor_id=floor_id,
            timestamp=datetime.now(timezone.utc),
            node_risks=node_risks,
            global_risk_level=global_level,
            active_hazards_count=active_hazards_count,
        )

    def _classify_global_risk(self, highest_risk: float) -> RiskLevel:
        """Classify aggregate risk based on configured thresholds."""
        lvls = self.config.levels
        if highest_risk >= lvls.get("critical_threshold", 0.75):
            return RiskLevel.CRITICAL
        elif highest_risk >= lvls.get("high_max", 0.50):
            return RiskLevel.HIGH
        elif highest_risk >= lvls.get("medium_max", 0.25):
            return RiskLevel.MEDIUM
        else:
            return RiskLevel.LOW
