"""
Domain entity models for PHOENIX.
Pure business data structures independent of web framework or ORM implementations.
"""

from datetime import datetime, timezone
from typing import Any, Optional
from pydantic import BaseModel, Field, field_validator

from app.domain.enums import (
    CameraStatus,
    DetectionType,
    IncidentSeverity,
    IncidentStatus,
    RiskLevel,
    RouteStatus,
    RoutingMode,
    SmokeGrowthTrend,
    UserRole,
)


class Point2D(BaseModel):
    """2D Cartesian point representation (e.g. image pixel or floorplan meter coordinate)."""
    x: float
    y: float


class BoundingBox(BaseModel):
    """Normalized or pixel bounding box [x1, y1, x2, y2]."""
    x1: float
    y1: float
    x2: float
    y2: float

    @property
    def width(self) -> float:
        return max(0.0, self.x2 - self.x1)

    @property
    def height(self) -> float:
        return max(0.0, self.y2 - self.y1)

    @property
    def area(self) -> float:
        return self.width * self.height

    @property
    def center(self) -> Point2D:
        return Point2D(x=(self.x1 + self.x2) / 2.0, y=(self.y1 + self.y2) / 2.0)

    @property
    def ground_point(self) -> Point2D:
        """Representative bottom-center contact point on ground."""
        return Point2D(x=(self.x1 + self.x2) / 2.0, y=self.y2)


class Detection(BaseModel):
    """Structured object detection produced by perception."""
    detection_id: Optional[str] = None
    job_id: Optional[str] = None
    frame_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    camera_id: str
    class_name: DetectionType
    confidence: float
    bbox: BoundingBox
    floor_point: Optional[Point2D] = None
    model_version: str = "yolov11-dual"


class SmokeObservation(BaseModel):
    """Temporal tracking record for observed smoke region."""
    observation_id: str
    camera_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    area_px2: float
    delta_area_px2: float = 0.0
    dt_seconds: float = 0.0
    growth_rate_px2_per_sec: float = 0.0
    smoothed_growth_rate: float = 0.0
    trend: SmokeGrowthTrend = SmokeGrowthTrend.UNKNOWN
    confidence: float = 0.0


class CalibrationPoint(BaseModel):
    """Pairing of image pixel coordinate to corresponding floorplan ground coordinate."""
    image_point: Point2D
    floor_point: Point2D


class Calibration(BaseModel):
    """Camera-specific homography transformation parameters."""
    calibration_id: str
    camera_id: str
    building_id: str
    floor_id: str
    matrix_3x3: list[list[float]] # 3x3 homography matrix
    points: list[CalibrationPoint] = Field(default_factory=list)
    version: int = 1
    is_valid: bool = True
    reprojection_error: float = 0.0
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Camera(BaseModel):
    """Monitored camera metadata and state."""
    camera_id: str
    organization_id: str
    building_id: str
    floor_id: str
    name: str
    source_uri: str
    status: CameraStatus = CameraStatus.ONLINE
    monitored_nodes: list[str] = Field(default_factory=list)
    calibration: Optional[Calibration] = None
    last_seen_at: Optional[datetime] = None


class Floor(BaseModel):
    """Floor metadata and coordinate boundaries."""
    floor_id: str
    building_id: str
    floor_number: int
    name: str
    width_meters: float
    height_meters: float
    floorplan_image_url: Optional[str] = None


class Building(BaseModel):
    """Physical building entity containing floors and navigation assets."""
    building_id: str
    organization_id: str
    name: str
    address: str
    floors: list[Floor] = Field(default_factory=list)


class NavigationNode(BaseModel):
    """Topological node in the building navigation graph."""
    node_id: str
    building_id: str
    floor_id: str
    label: str
    node_type: str = "corridor" # 'room', 'corridor', 'stairs', 'exit', 'hazard_zone'
    x: float
    y: float
    is_exit: bool = False
    capacity: int = 100


class NavigationEdge(BaseModel):
    """Directed or undirected navigable connection between two nodes."""
    edge_id: str
    building_id: str
    floor_id: str
    from_node: str
    to_node: str
    length_meters: float
    is_stairs: bool = False
    is_blocked: bool = False
    hazard_score: float = 0.0 # [0.0, 1.0]
    occupancy_count: int = 0
    predicted_blockage_score: float = 0.0 # [0.0, 1.0]


class RouteCostReason(BaseModel):
    """Auditable decomposition of evacuation route cost components."""
    distance_cost: float
    hazard_cost: float
    occupancy_cost: float
    predicted_blockage_cost: float
    total_cost: float


class RouteRecommendation(BaseModel):
    """Computed deterministic evacuation route recommendation."""
    route_id: str
    job_id: Optional[str] = None
    building_id: str
    floor_id: str
    graph_version: str = "1.0.0"
    origin_node: str
    destination_node: str
    path_nodes: list[str] = Field(default_factory=list)
    path_edges: list[str] = Field(default_factory=list)
    status: RouteStatus = RouteStatus.VALID
    eta_seconds: float = 0.0
    total_cost: float = 0.0
    cost_breakdown: RouteCostReason
    algorithm_version: str = "dijkstra_v1"
    calculation_assumptions: dict[str, Any] = Field(default_factory=dict)
    is_degraded: bool = False
    computed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RiskSnapshot(BaseModel):
    """Point-in-time spatial risk state across all navigation nodes."""
    snapshot_id: str
    building_id: str
    floor_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    node_risks: dict[str, float] = Field(default_factory=dict) # node_id -> risk [0.0, 1.0]
    global_risk_level: RiskLevel = RiskLevel.LOW
    active_hazards_count: int = 0


class Incident(BaseModel):
    """Emergency incident lifecycle record."""
    incident_id: str
    organization_id: str
    building_id: str
    floor_id: str
    status: IncidentStatus = IncidentStatus.REPORTED
    severity: IncidentSeverity = IncidentSeverity.LOW
    title: str
    description: Optional[str] = None
    hazard_origin_node: Optional[str] = None
    affected_nodes: list[str] = Field(default_factory=list)
    declared_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    resolved_at: Optional[datetime] = None


class User(BaseModel):
    """User account entity."""
    user_id: str
    organization_id: str
    email: str
    hashed_password: str
    full_name: str
    role: UserRole = UserRole.OCCUPANT
    is_active: bool = True
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class Organization(BaseModel):
    """Tenant isolation entity."""
    organization_id: str
    name: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class AuditEvent(BaseModel):
    """Immutable audit trail log for security and route decisions."""
    audit_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    organization_id: str
    user_id: Optional[str] = None
    action: str
    entity_type: str
    entity_id: str
    before_state: Optional[dict[str, Any]] = None
    after_state: Optional[dict[str, Any]] = None
    reason: Optional[str] = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class EvaluationResult(BaseModel):
    """Benchmark outcome for comparing routing algorithms under emergency scenarios."""
    run_id: str
    scenario_name: str
    mode: RoutingMode
    total_cost: float
    travel_time_seconds: float
    route_blocked: bool
    reroute_count: int
    time_to_first_reroute_seconds: Optional[float] = None
    route_length_meters: float
    prediction_lead_time_seconds: Optional[float] = None
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ScaleReference(BaseModel):
    """Calibrated physical distance reference for floorplan images."""
    point_a: Point2D
    point_b: Point2D
    known_distance_meters: float
    pixel_distance: float
    meters_per_pixel: float
    is_calibrated: bool = True
    calibration_method: str = "reference_points"  # "scale_bar", "reference_points", "bim_metadata", "manual"
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class SpatialRegion(BaseModel):
    """Architectural room, corridor, hall, or exit boundary polygon."""
    region_id: str
    building_id: str
    floor_id: str
    name: str
    region_type: str = "ROOM"  # SpatialRegionType enum value
    polygon: list[Point2D] = Field(default_factory=list)
    center: Point2D
    width_meters: Optional[float] = None
    height_meters: Optional[float] = None
    area_sqm: Optional[float] = None
    is_exit: bool = False
    is_navigable: bool = True
    capacity: int = 50
    monitored_cameras: list[str] = Field(default_factory=list)
    provenance: str = "CONFIGURED"  # MeasurementProvenance enum value


class FloorplanModel(BaseModel):
    """Complete dynamic spatial model of a building floor."""
    floorplan_id: str
    building_id: str
    floor_id: str
    name: str
    image_url: Optional[str] = None
    image_width_px: int = 1000
    image_height_px: int = 800
    scale_reference: Optional[ScaleReference] = None
    physical_width_meters: Optional[float] = None
    physical_height_meters: Optional[float] = None
    is_scale_calibrated: bool = False
    graph_version: str = "1.0.0"
    regions: list[SpatialRegion] = Field(default_factory=list)
    walls: list[list[Point2D]] = Field(default_factory=list)
    doors: list[Point2D] = Field(default_factory=list)
    exits: list[Point2D] = Field(default_factory=list)
    nodes: list[NavigationNode] = Field(default_factory=list)
    edges: list[NavigationEdge] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class VisualGeometryFeature(BaseModel):
    """Spatial metrics extracted directly from camera video frames."""
    frame_id: str
    camera_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    bounding_box_pixels: BoundingBox
    ground_contact_pixel: Point2D
    relative_screen_position: Point2D  # [0.0..1.0, 0.0..1.0]
    hazard_pixel_area: float
    expansion_velocity_px_per_sec: float = 0.0
    detected_class: str
    confidence: float
    vanishing_point: Optional[Point2D] = None
    provenance: str = "MEASURED"


class FloorHazardObservation(BaseModel):
    """Spatial hazard mapped onto shared building floor coordinates with multi-camera fusion."""
    observation_id: str
    building_id: str
    floor_id: str
    camera_id: str
    hazard_type: str  # "fire", "smoke"
    confidence: float
    floor_point: Point2D  # in floor coordinate system (meters or normalized)
    region_id: Optional[str] = None
    nearest_node_id: Optional[str] = None
    fused_from_cameras: list[str] = Field(default_factory=list)
    spatial_uncertainty_radius_meters: float = 1.0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    provenance: str = "CALIBRATED"

