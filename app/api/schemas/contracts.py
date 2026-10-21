"""
FastAPI Request/Response Schemas for PHOENIX API endpoints.
Strict Pydantic models for validation and serialization.
"""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel, Field

from app.domain.enums import (
    CameraStatus,
    IncidentSeverity,
    IncidentStatus,
    RiskLevel,
    RouteStatus,
    UserRole,
)


class LoginRequest(BaseModel):
    email: str = Field(..., json_schema_extra={"example": "admin@phoenix.local"})
    password: str = Field(..., json_schema_extra={"example": "SecurePass123!"})


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user_id: str
    role: UserRole
    organization_id: str
    expires_in_seconds: int
    refresh_token: Optional[str] = None


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: Optional[str] = None


class CreateUserRequest(BaseModel):
    email: str
    password: str
    full_name: str
    role: UserRole = UserRole.OCCUPANT
    organization_id: Optional[str] = None


class UpdateUserStatusRequest(BaseModel):
    is_active: bool


class UserResponse(BaseModel):
    user_id: str
    organization_id: str
    email: str
    full_name: str
    role: UserRole
    is_active: bool
    created_at: datetime


class HealthCheckResponse(BaseModel):
    status: str = "HEALTHY"
    timestamp: datetime
    version: str = "1.0.0"
    environment: str
    services: dict[str, str]


class ReadinessResponse(BaseModel):
    ready: bool = True
    ai_status: str = "OPERATIONAL"
    persistence_status: str = "OPERATIONAL"
    timestamp: datetime


class Point2DSchema(BaseModel):
    x: float
    y: float


class NavigationNodeSchema(BaseModel):
    node_id: str
    building_id: str
    floor_id: str
    label: str
    node_type: str
    x: float
    y: float
    is_exit: bool
    capacity: int


class NavigationEdgeSchema(BaseModel):
    edge_id: str
    building_id: str
    floor_id: str
    from_node: str
    to_node: str
    length_meters: float
    is_stairs: bool
    is_blocked: bool
    hazard_score: float
    occupancy_count: int
    predicted_blockage_score: float


class FloorSchema(BaseModel):
    floor_id: str
    building_id: str
    floor_number: int
    name: str
    width_meters: float
    height_meters: float
    floorplan_image_url: Optional[str] = None


class BuildingResponse(BaseModel):
    building_id: str
    organization_id: str
    name: str
    address: str
    floors: list[FloorSchema] = Field(default_factory=list)


class CameraResponse(BaseModel):
    camera_id: str
    organization_id: str
    building_id: str
    floor_id: str
    name: str
    source_uri: str
    status: CameraStatus
    monitored_nodes: list[str] = Field(default_factory=list)
    has_calibration: bool = False
    last_seen_at: Optional[datetime] = None


class IncidentResponse(BaseModel):
    incident_id: str
    organization_id: str
    building_id: str
    floor_id: str
    status: IncidentStatus
    severity: IncidentSeverity
    title: str
    description: Optional[str] = None
    hazard_origin_node: Optional[str] = None
    affected_nodes: list[str] = Field(default_factory=list)
    declared_at: datetime
    updated_at: datetime
    resolved_at: Optional[datetime] = None


class RouteCostReasonSchema(BaseModel):
    distance_cost: float
    hazard_cost: float
    occupancy_cost: float
    predicted_blockage_cost: float
    total_cost: float


class RouteRecommendationResponse(BaseModel):
    route_id: str
    job_id: Optional[str] = None
    building_id: str
    floor_id: str
    graph_version: str = "1.0.0"
    origin_node: str
    destination_node: str
    path_nodes: list[str]
    path_edges: list[str]
    status: RouteStatus
    eta_seconds: float
    total_cost: float
    cost_breakdown: RouteCostReasonSchema
    algorithm_version: str
    calculation_assumptions: dict[str, Any] = Field(default_factory=dict)
    is_degraded: bool
    computed_at: datetime


class VideoSourceResponse(BaseModel):
    video_id: str
    organization_id: str
    original_filename: str
    stored_filename: str
    storage_path: str
    mime_type: str
    file_size_bytes: int
    sha256_checksum: str
    duration_seconds: float
    fps: float
    width: int
    height: int
    uploaded_by_user_id: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    created_at: str
    updated_at: Optional[str] = None


class ProcessingJobResponse(BaseModel):
    job_id: str
    video_id: str
    organization_id: str
    created_by_user_id: Optional[str] = None
    status: str
    progress_percent: float
    current_stage: str
    frames_processed: int
    total_frames: int
    detections_count: int
    fire_detected: bool
    smoke_detected: bool
    max_risk_level: str
    error_code: Optional[str] = None
    error_message: Optional[str] = None
    retry_count: int
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    execution_time_seconds: Optional[float] = None
    annotated_video_path: Optional[str] = None
    output_metadata: Optional[dict[str, Any]] = None
    created_at: str
    updated_at: str
