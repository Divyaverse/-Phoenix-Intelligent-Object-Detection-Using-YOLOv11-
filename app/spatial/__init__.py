"""Spatial intelligence module: homography mapping, dynamic floorplans, multi-camera fusion, and spatial management."""

from app.spatial.calibration import CalibrationService
from app.spatial.floorplan_parser import FloorplanProcessor
from app.spatial.heatmap import SpatialHeatmapGenerator
from app.spatial.homography import PlanarHomographyMapper
from app.spatial.multi_camera_fusion import MultiCameraSpatialFusionEngine
from app.spatial.spatial_manager import SpatialManager, spatial_manager
from app.spatial.video_geometry import VideoGeometryExtractor

__all__ = [
    "CalibrationService",
    "FloorplanProcessor",
    "SpatialHeatmapGenerator",
    "PlanarHomographyMapper",
    "MultiCameraSpatialFusionEngine",
    "SpatialManager",
    "spatial_manager",
    "VideoGeometryExtractor",
]
