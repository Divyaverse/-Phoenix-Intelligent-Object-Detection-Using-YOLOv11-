"""
Multi-Floor Spatial Manager for PHOENIX.
Maintains hierarchical Building -> Floor -> FloorplanModel registry, coordinates
camera mappings, and supplies dynamic navigation graphs to routing engines.
"""

from datetime import datetime, timezone
import logging
from typing import Optional

from app.domain.models import (
    Calibration,
    Camera,
    FloorHazardObservation,
    FloorplanModel,
    NavigationEdge,
    NavigationNode,
    Point2D,
    ScaleReference,
    SpatialRegion,
)
from app.graph.navigation_graph import NavigationGraph
from app.spatial.floorplan_parser import FloorplanProcessor
from app.spatial.multi_camera_fusion import MultiCameraSpatialFusionEngine

logger = logging.getLogger("phoenix.spatial")


class SpatialManager:
    """
    Central spatial registry and coordinator for multi-building, multi-floor environments.
    """

    def __init__(self) -> None:
        # building_id -> floor_id -> FloorplanModel
        self._floorplans: dict[str, dict[str, FloorplanModel]] = {}
        # building_id -> floor_id -> NavigationGraph
        self._nav_graphs: dict[str, dict[str, NavigationGraph]] = {}
        # camera_id -> Calibration
        self._camera_calibrations: dict[str, Calibration] = {}
        # building_id -> floor_id -> list[FloorHazardObservation]
        self._active_floor_hazards: dict[str, dict[str, list[FloorHazardObservation]]] = {}

        self.processor = FloorplanProcessor()
        self.fusion_engine = MultiCameraSpatialFusionEngine(floorplan_processor=self.processor)

    def register_floorplan(self, floorplan: FloorplanModel) -> None:
        """Register or update a dynamic floorplan model for a specific building floor."""
        b_id = floorplan.building_id
        f_id = floorplan.floor_id

        if b_id not in self._floorplans:
            self._floorplans[b_id] = {}
            self._nav_graphs[b_id] = {}
            self._active_floor_hazards[b_id] = {}

        self._floorplans[b_id][f_id] = floorplan

        # Reconstruct dynamic NavigationGraph from floorplan nodes & edges
        nav_graph = NavigationGraph.from_nodes_and_edges(
            building_id=b_id,
            floor_id=f_id,
            nodes=floorplan.nodes,
            edges=floorplan.edges,
        )
        self._nav_graphs[b_id][f_id] = nav_graph
        logger.info(f"Registered dynamic floorplan for {b_id}/{f_id} with {len(floorplan.nodes)} nodes.")

    def get_floorplan(self, building_id: str, floor_id: str) -> Optional[FloorplanModel]:
        """Retrieve dynamic floorplan model for building and floor."""
        return self._floorplans.get(building_id, {}).get(floor_id)

    def get_navigation_graph(self, building_id: str, floor_id: str) -> Optional[NavigationGraph]:
        """Retrieve active dynamic navigation graph."""
        return self._nav_graphs.get(building_id, {}).get(floor_id)

    def register_camera_calibration(self, calibration: Calibration) -> None:
        """Register camera homography calibration."""
        self._camera_calibrations[calibration.camera_id] = calibration

    def get_camera_calibration(self, camera_id: str) -> Optional[Calibration]:
        """Retrieve camera homography calibration."""
        return self._camera_calibrations.get(camera_id)

    def update_floor_hazards(
        self,
        building_id: str,
        floor_id: str,
        camera_detections: list[tuple[str, list, Optional[Calibration]]],
    ) -> list[FloorHazardObservation]:
        """
        Fuse simultaneous detections from multiple cameras on the target floor
        and update the shared floor hazard map.
        """
        floorplan = self.get_floorplan(building_id, floor_id)
        fused = self.fusion_engine.fuse_camera_detections(
            building_id=building_id,
            floor_id=floor_id,
            camera_detections=camera_detections,
            floorplan=floorplan,
        )

        if building_id not in self._active_floor_hazards:
            self._active_floor_hazards[building_id] = {}

        self._active_floor_hazards[building_id][floor_id] = fused
        return fused

    def get_active_hazards(self, building_id: str, floor_id: str) -> list[FloorHazardObservation]:
        """Retrieve all current fused hazards for a floor."""
        return self._active_floor_hazards.get(building_id, {}).get(floor_id, [])

    def clear_hazards(self, building_id: str, floor_id: str) -> None:
        """Clear all active spatial hazards for a floor upon resolution."""
        if building_id in self._active_floor_hazards and floor_id in self._active_floor_hazards[building_id]:
            self._active_floor_hazards[building_id][floor_id] = []


# Global singleton instance
spatial_manager = SpatialManager()
