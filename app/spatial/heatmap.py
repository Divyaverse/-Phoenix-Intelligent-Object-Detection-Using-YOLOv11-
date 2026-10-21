"""
Spatial risk grid and heatmap generator for floorplan visualization.
"""

from typing import Any, Optional
import numpy as np
from pydantic import BaseModel, Field

from app.core.config import SpatialConfig, settings
from app.domain.models import Point2D


class HeatmapGrid(BaseModel):
    """2D rasterized risk heatmap for client rendering."""
    floor_id: str
    width_meters: float
    height_meters: float
    resolution_meters: float
    cols: int
    rows: int
    grid_values: list[list[float]] # 2D array of risk intensities in [0.0, 1.0]


class SpatialHeatmapGenerator:
    """
    Renders continuous 2D spatial risk distributions over floorplan coordinates
    using Gaussian kernel decay around observed hazard centroids.
    """

    def __init__(self, config: Optional[SpatialConfig] = None) -> None:
        self.config = config or settings.spatial

    def generate_grid(
        self,
        floor_id: str,
        width_meters: float,
        height_meters: float,
        hazards: list[tuple[Point2D, float]], # List of (floor_point, intensity [0,1])
        decay_radius_meters: float = 4.0,
    ) -> HeatmapGrid:
        """
        Generate a 2D matrix of risk intensities sampled across floorplan grid cells.
        """
        res = self.config.grid_resolution_meters
        cols = max(1, int(np.ceil(width_meters / res)))
        rows = max(1, int(np.ceil(height_meters / res)))

        grid = np.zeros((rows, cols), dtype=np.float32)

        if not hazards:
            return HeatmapGrid(
                floor_id=floor_id,
                width_meters=width_meters,
                height_meters=height_meters,
                resolution_meters=res,
                cols=cols,
                rows=rows,
                grid_values=grid.tolist(),
            )

        # Coordinate arrays for vectorized distance computation
        x_coords = np.linspace(0, width_meters, cols)
        y_coords = np.linspace(0, height_meters, rows)
        X, Y = np.meshgrid(x_coords, y_coords)

        sigma = max(0.5, decay_radius_meters / 2.0)

        for point, intensity in hazards:
            if intensity <= 0.0:
                continue
            # Euclidean distance squared
            dist_sq = (X - point.x) ** 2 + (Y - point.y) ** 2
            # Gaussian decay kernel: intensity * exp(-dist^2 / (2 * sigma^2))
            influence = intensity * np.exp(-dist_sq / (2.0 * sigma * sigma))
            grid = np.maximum(grid, influence)

        # Clip intensities strictly to [0.0, 1.0]
        grid = np.clip(grid, 0.0, 1.0)
        grid_rounded = np.round(grid, 3).tolist()

        return HeatmapGrid(
            floor_id=floor_id,
            width_meters=width_meters,
            height_meters=height_meters,
            resolution_meters=res,
            cols=cols,
            rows=rows,
            grid_values=grid_rounded,
        )
