"""
Spatial & Dynamic Floorplan API Routes for PHOENIX.
Provides floorplan image extraction, scale calibration, dynamic graph configuration,
and multi-camera spatial telemetry endpoints.
"""

from datetime import datetime, timezone
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field

from app.api.dependencies import get_current_user_payload, require_role
from app.db.repositories import SQLiteFloorplanRepository
from app.domain.enums import UserRole
from app.domain.models import (
    Calibration,
    CalibrationPoint,
    FloorplanModel,
    NavigationEdge,
    NavigationNode,
    Point2D,
    ScaleReference,
    SpatialRegion,
)
from app.spatial.calibration import CalibrationService
from app.spatial.floorplan_parser import FloorplanProcessor
from app.spatial.multi_camera_fusion import MultiCameraSpatialFusionEngine
from app.spatial.spatial_manager import spatial_manager

router = APIRouter(prefix="/spatial", tags=["Spatial & Dynamic Floorplans"])
floorplan_repo = SQLiteFloorplanRepository()
processor = FloorplanProcessor()
cal_service = CalibrationService()
fusion_engine = MultiCameraSpatialFusionEngine()


# --- Request & Response Schemas ---

class ScaleCalibrationRequest(BaseModel):
    point_a: Point2D
    point_b: Point2D
    known_distance_meters: float
    calibration_method: str = "reference_points"


class FloorplanExtractRequest(BaseModel):
    building_id: str
    floor_id: str
    image_path: str
    name: Optional[str] = "Extracted Floorplan"
    scale_reference: Optional[ScaleReference] = None


class FloorplanConfigureRequest(BaseModel):
    building_id: str
    floor_id: str
    name: str
    image_url: Optional[str] = None
    image_width_px: int = 1000
    image_height_px: int = 800
    physical_width_meters: Optional[float] = None
    physical_height_meters: Optional[float] = None
    scale_reference: Optional[ScaleReference] = None
    regions: list[SpatialRegion] = Field(default_factory=list)
    walls: list[list[Point2D]] = Field(default_factory=list)
    doors: list[Point2D] = Field(default_factory=list)
    exits: list[Point2D] = Field(default_factory=list)
    nodes: list[NavigationNode] = Field(default_factory=list)
    edges: list[NavigationEdge] = Field(default_factory=list)


class CameraCalibrationRequest(BaseModel):
    camera_id: str
    building_id: str
    floor_id: str
    calibration_points: list[CalibrationPoint]


# --- Endpoints ---

@router.post("/calibrate-scale", response_model=ScaleReference)
def calibrate_scale(
    request: ScaleCalibrationRequest,
    payload: dict = Depends(require_role([UserRole.SUPERADMIN, UserRole.BUILDING_MANAGER])),
) -> ScaleReference:
    """Calibrate floorplan pixel-to-meter scale using two known reference coordinates."""
    try:
        return processor.calibrate_scale(
            point_a=request.point_a,
            point_b=request.point_b,
            known_distance_meters=request.known_distance_meters,
            calibration_method=request.calibration_method,
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))


@router.post("/floorplans/extract", response_model=FloorplanModel)
def extract_floorplan(
    request: FloorplanExtractRequest,
    payload: dict = Depends(require_role([UserRole.SUPERADMIN, UserRole.BUILDING_MANAGER])),
) -> FloorplanModel:
    """Run Computer Vision wall/room extraction on a floorplan image and generate navigation topology."""
    try:
        model = processor.process_floorplan_image(
            image_path=request.image_path,
            building_id=request.building_id,
            floor_id=request.floor_id,
            name=request.name or "Extracted Floorplan",
            scale_reference=request.scale_reference,
        )
        floorplan_repo.save(model)
        spatial_manager.register_floorplan(model)
        return model
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Floorplan extraction failed: {str(e)}")


@router.post("/floorplans/{building_id}/{floor_id}", response_model=FloorplanModel)
def save_floorplan_configuration(
    building_id: str,
    floor_id: str,
    config: FloorplanConfigureRequest,
    payload: dict = Depends(require_role([UserRole.SUPERADMIN, UserRole.BUILDING_MANAGER])),
) -> FloorplanModel:
    """Save or update structured floorplan regions, scale, walls, doors, exits, and graph topology."""
    model = FloorplanModel(
        floorplan_id=f"fp_{floor_id}",
        building_id=building_id,
        floor_id=floor_id,
        name=config.name,
        image_url=config.image_url,
        image_width_px=config.image_width_px,
        image_height_px=config.image_height_px,
        scale_reference=config.scale_reference,
        physical_width_meters=config.physical_width_meters,
        physical_height_meters=config.physical_height_meters,
        is_scale_calibrated=config.scale_reference is not None and config.scale_reference.is_calibrated,
        regions=config.regions,
        walls=config.walls,
        doors=config.doors,
        exits=config.exits,
        nodes=config.nodes,
        edges=config.edges,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    floorplan_repo.save(model)
    spatial_manager.register_floorplan(model)
    return model


@router.get("/floorplans/{building_id}/{floor_id}", response_model=FloorplanModel)
def get_floorplan(
    building_id: str,
    floor_id: str,
    payload: dict = Depends(get_current_user_payload),
) -> FloorplanModel:
    """Retrieve dynamic floorplan model, scale metadata, and topological navigation graph."""
    db_fp = floorplan_repo.get_by_floor(building_id, floor_id)
    if db_fp:
        spatial_manager.register_floorplan(db_fp)
        return db_fp

    # Fallback to authentic main corridor model if not yet explicitly saved
    fallback_model = processor.create_main_corridor_floorplan(building_id, floor_id)
    floorplan_repo.save(fallback_model)
    spatial_manager.register_floorplan(fallback_model)
    return fallback_model


@router.post("/cameras/calibrate", response_model=Calibration)
def calibrate_camera(
    request: CameraCalibrationRequest,
    payload: dict = Depends(require_role([UserRole.SUPERADMIN, UserRole.BUILDING_MANAGER])),
) -> Calibration:
    """Calibrate camera homography transformation parameters from pixel to floor coordinates."""
    try:
        calib = cal_service.create_calibration(
            camera_id=request.camera_id,
            building_id=request.building_id,
            floor_id=request.floor_id,
            points=request.calibration_points,
        )
        spatial_manager.register_camera_calibration(calib)
        return calib
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Camera calibration failed: {str(e)}")


@router.get("/cameras/{camera_id}/verify-mapping")
def verify_camera_mapping(
    camera_id: str,
    payload: dict = Depends(get_current_user_payload),
) -> dict:
    """
    Verify spatial mapping and planar homography conditioning for a given camera.
    Returns status (VERIFIED/DEGRADED), condition number, reprojection error,
    and explicitly categorizes verified vs unverified spatial elements.
    """
    calib = spatial_manager.get_camera_calibration(camera_id)
    if not calib:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"No active calibration for camera {camera_id}")
    return cal_service.verify_mapping(calib)
