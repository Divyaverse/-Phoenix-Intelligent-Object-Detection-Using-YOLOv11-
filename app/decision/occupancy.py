"""
Approximate Occupancy Estimator for PHOENIX.
"""

from typing import Optional
import numpy as np

from app.core.config import OccupancyConfig, settings
from app.domain.enums import DetectionType
from app.domain.interfaces import OccupancyEstimator
from app.domain.models import Detection, NavigationNode


class ApproximateOccupancyEstimator(OccupancyEstimator):
    """
    Aggregates visual person detections and maps them onto topological navigation nodes.
    Represents approximate headcount, not certified crowd density dynamics.
    """

    def __init__(self, config: Optional[OccupancyConfig] = None) -> None:
        self.config = config or settings.occupancy

    def estimate_node_occupancies(
        self,
        nodes: list[NavigationNode],
        person_detections: list[Detection],
    ) -> dict[str, int]:
        """
        Map each person detection to its closest navigation node and count occupants.
        """
        occupancy_map: dict[str, int] = {n.node_id: 0 for n in nodes}

        valid_persons = [
            d for d in person_detections
            if d.class_name == DetectionType.PERSON and d.floor_point is not None
        ]

        if not valid_persons or not nodes:
            return occupancy_map

        for person in valid_persons:
            pt = person.floor_point
            if pt is None:
                continue

            # Find closest node via Euclidean distance
            best_node_id = None
            min_dist_sq = float("inf")

            for node in nodes:
                dist_sq = (node.x - pt.x) ** 2 + (node.y - pt.y) ** 2
                if dist_sq < min_dist_sq:
                    min_dist_sq = dist_sq
                    best_node_id = node.node_id

            if best_node_id is not None:
                occupancy_map[best_node_id] += 1

        return occupancy_map
