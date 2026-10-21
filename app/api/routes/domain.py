from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.dependencies import get_current_user_payload, require_role
from app.api.schemas.contracts import (
    BuildingResponse,
    CameraResponse,
    FloorSchema,
    IncidentResponse,
    RouteCostReasonSchema,
    RouteRecommendationResponse,
)
from app.db.repositories import (
    SQLiteAuditEventRepository,
    SQLiteBuildingRepository,
    SQLiteCameraRepository,
    SQLiteDetectionRepository,
    SQLiteIncidentRepository,
    SQLiteRiskEventRepository,
    SQLiteRouteRecommendationRepository,
)
from app.domain.enums import (
    CameraStatus,
    IncidentSeverity,
    IncidentStatus,
    RouteStatus,
    UserRole,
)

router = APIRouter(tags=["Domain Intelligence"])

building_repo = SQLiteBuildingRepository()
camera_repo = SQLiteCameraRepository()
incident_repo = SQLiteIncidentRepository()
route_repo = SQLiteRouteRecommendationRepository()
detection_repo = SQLiteDetectionRepository()
risk_repo = SQLiteRiskEventRepository()
audit_repo = SQLiteAuditEventRepository()


@router.get("/incidents/current", response_model=Optional[IncidentResponse])
def get_current_incident(
    building_id: Optional[str] = Query(None, description="Optional building filter"),
    payload: dict = Depends(get_current_user_payload),
) -> Optional[IncidentResponse]:
    """
    Retrieve active emergency incident for authorized scope.
    Returns None if all systems are normal and no genuine hazard is active.
    """
    target_bldg = building_id or "bldg-hq-01"
    db_incident = incident_repo.get_current_by_building(target_bldg)
    if db_incident and db_incident.status not in (IncidentStatus.CLOSED, IncidentStatus.RESOLVED):
        return IncidentResponse(
            incident_id=db_incident.incident_id,
            organization_id=db_incident.organization_id,
            building_id=db_incident.building_id,
            floor_id=db_incident.floor_id,
            status=db_incident.status,
            severity=db_incident.severity,
            title=db_incident.title,
            description=db_incident.description,
            hazard_origin_node=db_incident.hazard_origin_node,
            affected_nodes=db_incident.affected_nodes,
            declared_at=db_incident.declared_at,
            updated_at=db_incident.updated_at,
            resolved_at=db_incident.resolved_at,
        )
    return None


@router.get("/routes/current", response_model=Optional[RouteRecommendationResponse])
def get_current_route(
    origin: str = Query("room_101", description="Origin navigation node"),
    building_id: str = Query("bldg-hq-01", description="Target building ID"),
    payload: dict = Depends(get_current_user_payload),
) -> Optional[RouteRecommendationResponse]:
    """
    Retrieve current deterministic evacuation route recommendation.
    Returns None if no emergency evacuation route is computed or needed.
    """
    db_route = route_repo.get_latest_route(building_id, origin)
    if not db_route:
        db_route = route_repo.get_latest_route_for_building(building_id)

    if db_route:
        return RouteRecommendationResponse(
            route_id=db_route.route_id,
            building_id=db_route.building_id,
            floor_id=db_route.floor_id,
            origin_node=db_route.origin_node,
            destination_node=db_route.destination_node,
            path_nodes=db_route.path_nodes,
            path_edges=db_route.path_edges,
            status=db_route.status,
            eta_seconds=db_route.eta_seconds,
            total_cost=db_route.total_cost,
            cost_breakdown=RouteCostReasonSchema(**db_route.cost_breakdown.model_dump()),
            algorithm_version=db_route.algorithm_version,
            is_degraded=db_route.is_degraded,
            computed_at=db_route.computed_at,
        )
    return None


@router.get("/buildings/{building_id}", response_model=BuildingResponse)
def get_building(
    building_id: str,
    payload: dict = Depends(get_current_user_payload),
) -> BuildingResponse:
    """Get building hierarchy, floor layout, and node configurations."""
    db_bldg = building_repo.get(building_id)
    if db_bldg:
        return BuildingResponse(
            building_id=db_bldg.building_id,
            organization_id=db_bldg.organization_id,
            name=db_bldg.name,
            address=db_bldg.address,
            floors=[
                FloorSchema(
                    floor_id=f.floor_id,
                    building_id=f.building_id,
                    floor_number=f.floor_number,
                    name=f.name,
                    width_meters=f.width_meters,
                    height_meters=f.height_meters,
                    floorplan_image_url=f.floorplan_image_url,
                )
                for f in db_bldg.floors
            ] if hasattr(db_bldg, "floors") and db_bldg.floors else [
                FloorSchema(
                    floor_id="fl-01",
                    building_id=db_bldg.building_id,
                    floor_number=1,
                    name="Ground Floor Main Lobby",
                    width_meters=50.0,
                    height_meters=40.0,
                )
            ],
        )

    # Fallback to standard building definition if DB not yet queried
    return BuildingResponse(
        building_id=building_id,
        organization_id="org-phoenix-main",
        name="Phoenix Innovation Center",
        address="100 Tech Blvd, Building A",
        floors=[
            FloorSchema(
                floor_id="fl-01",
                building_id=building_id,
                floor_number=1,
                name="Ground Floor Main Lobby",
                width_meters=50.0,
                height_meters=40.0,
            )
        ],
    )


@router.get("/cameras", response_model=list[CameraResponse])
def get_cameras(
    building_id: Optional[str] = Query(None),
    payload: dict = Depends(require_role([UserRole.SUPERADMIN, UserRole.BUILDING_MANAGER, UserRole.FIRST_RESPONDER])),
) -> list[CameraResponse]:
    """List monitored cameras and calibration state."""
    target_bldg = building_id or "bldg-hq-01"
    db_cams = camera_repo.list_by_building(target_bldg)
    if db_cams:
        return [
            CameraResponse(
                camera_id=c.camera_id,
                organization_id=c.organization_id,
                building_id=c.building_id,
                floor_id=c.floor_id,
                name=c.name,
                source_uri=c.source_uri,
                status=c.status,
                monitored_nodes=c.monitored_nodes,
                has_calibration=c.calibration is not None if hasattr(c, "calibration") else True,
                last_seen_at=c.last_seen_at,
            )
            for c in db_cams
        ]

    # Return default CCTV network for the facility (Primary: CAM-MAIN-01 with Main_video.mp4)
    return [
        CameraResponse(
            camera_id="CAM-MAIN-01",
            organization_id="org-phoenix-main",
            building_id=target_bldg,
            floor_id="fl-01",
            name="Central Corridor North View (Main CCTV)",
            source_uri="/videos/Main_video.mp4",
            status=CameraStatus.ONLINE,
            monitored_nodes=["node_corridor_mid", "node_east_alcove", "node_corridor_north"],
            has_calibration=True,
            last_seen_at=datetime.now(timezone.utc),
        ),
        CameraResponse(
            camera_id="CAM-MAIN-01-AI",
            organization_id="org-phoenix-main",
            building_id=target_bldg,
            floor_id="fl-01",
            name="Central Corridor (AI Detection Overlay)",
            source_uri="/videos/Main_video_annotated.mp4",
            status=CameraStatus.ONLINE,
            monitored_nodes=["node_corridor_mid", "node_east_alcove"],
            has_calibration=True,
            last_seen_at=datetime.now(timezone.utc),
        ),
        CameraResponse(
            camera_id="CAM-NORTH-01",
            organization_id="org-phoenix-main",
            building_id=target_bldg,
            floor_id="fl-01",
            name="North Corridor",
            source_uri="/videos/test 1.mp4",
            status=CameraStatus.ONLINE,
            monitored_nodes=["node_n1", "node_c1"],
            has_calibration=True,
            last_seen_at=datetime.now(timezone.utc),
        ),
        CameraResponse(
            camera_id="CAM-SOUTH-01",
            organization_id="org-phoenix-main",
            building_id=target_bldg,
            floor_id="fl-01",
            name="South Exit Corridor",
            source_uri="/videos/test2.mp4",
            status=CameraStatus.ONLINE,
            monitored_nodes=["node_s1", "exit_south"],
            has_calibration=True,
            last_seen_at=datetime.now(timezone.utc),
        ),
        CameraResponse(
            camera_id="CAM-HALL-01",
            organization_id="org-phoenix-main",
            building_id=target_bldg,
            floor_id="fl-01",
            name="Main Hall West",
            source_uri="/videos/test3.mp4",
            status=CameraStatus.ONLINE,
            monitored_nodes=["node_c1", "room_101"],
            has_calibration=True,
            last_seen_at=datetime.now(timezone.utc),
        ),
    ]


@router.get("/detections/recent")
def get_recent_detections(
    camera_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    payload: dict = Depends(get_current_user_payload),
) -> list[dict]:
    """Retrieve recent genuine YOLO detections from the database."""
    dets = detection_repo.list_recent(camera_id=camera_id, limit=limit)
    return [d.model_dump() for d in dets]


@router.get("/risk/current")
def get_current_risk(
    building_id: str = Query("bldg-hq-01"),
    payload: dict = Depends(get_current_user_payload),
) -> Optional[dict]:
    """Retrieve latest spatial risk snapshot from the database."""
    return risk_repo.get_latest(building_id)


@router.get("/events/history")
def get_event_history(
    limit: int = Query(50, ge=1, le=200),
    payload: dict = Depends(get_current_user_payload),
) -> list[dict]:
    """Retrieve persistent audit and domain event history."""
    return audit_repo.list_recent(limit=limit)

