"""
Domain enumeration types for PHOENIX.
"""

from enum import Enum


class DetectionType(str, Enum):
    """Supported detection object classes."""
    FIRE = "fire"
    SMOKE = "smoke"
    PERSON = "person"


class IncidentStatus(str, Enum):
    """Emergency incident lifecycle status."""
    REPORTED = "REPORTED"
    CONFIRMED = "CONFIRMED"
    EVACUATING = "EVACUATING"
    CONTAINED = "CONTAINED"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"


class IncidentSeverity(str, Enum):
    """Incident severity classification."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class CameraStatus(str, Enum):
    """Operational status of a camera feed."""
    ONLINE = "ONLINE"
    OFFLINE = "OFFLINE"
    DEGRADED = "DEGRADED"
    CALIBRATION_REQUIRED = "CALIBRATION_REQUIRED"


class RiskLevel(str, Enum):
    """Computed spatial or node risk level."""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"
    BLOCKED = "BLOCKED"


class UserRole(str, Enum):
    """Role-based access control roles."""
    SUPERADMIN = "SUPERADMIN"
    BUILDING_MANAGER = "BUILDING_MANAGER"
    FIRST_RESPONDER = "FIRST_RESPONDER"
    OCCUPANT = "OCCUPANT"


class JobStatus(str, Enum):
    """Lifecycle status of background video processing jobs."""
    QUEUED = "QUEUED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class RouteStatus(str, Enum):
    """Status of computed evacuation route recommendations."""
    VALID = "VALID"
    NO_VALID_ROUTE = "NO_VALID_ROUTE"
    NO_VALID_EXIT = "NO_VALID_EXIT"
    DEGRADED = "DEGRADED"


class SystemStatus(str, Enum):
    """Global platform health and readiness status."""
    HEALTHY = "HEALTHY"
    DEGRADED = "DEGRADED"
    CRITICAL = "CRITICAL"
    PERSISTENCE_UNAVAILABLE = "PERSISTENCE_UNAVAILABLE"


class SmokeGrowthTrend(str, Enum):
    """Temporal classification of smoke observation area changes."""
    STABLE = "STABLE"
    MODERATE_GROWTH = "MODERATE_GROWTH"
    RAPID_GROWTH = "RAPID_GROWTH"
    DECREASING = "DECREASING"
    UNKNOWN = "UNKNOWN"


class RoutingMode(str, Enum):
    """Evacuation routing evaluation modes."""
    STATIC = "STATIC"
    REACTIVE = "REACTIVE"
    PREDICTIVE = "PREDICTIVE"


class EventType(str, Enum):
    """Domain and realtime event types."""
    DETECTION_OBSERVED = "DETECTION_OBSERVED"
    SMOKE_GROWTH_ALERT = "SMOKE_GROWTH_ALERT"
    RISK_UPDATED = "RISK_UPDATED"
    ROUTE_CHANGED = "ROUTE_CHANGED"
    CAMERA_STATUS_CHANGED = "CAMERA_STATUS_CHANGED"
    INCIDENT_STATUS_CHANGED = "INCIDENT_STATUS_CHANGED"
    SYSTEM_ALERT = "SYSTEM_ALERT"
    FLOORPLAN_UPDATED = "FLOORPLAN_UPDATED"


class MeasurementProvenance(str, Enum):
    """Classification of spatial data origin and certainty."""
    MEASURED = "MEASURED"         # Directly measured from video/sensors (e.g. raw pixel bbox, timestamp)
    CALCULATED = "CALCULATED"     # Derived via visual geometry (e.g. ground contact point, pixel area)
    CALIBRATED = "CALIBRATED"     # Metric physical measurement via verified reference scale/homography
    CONFIGURED = "CONFIGURED"     # Explicitly provided by user/architectural blueprint
    ESTIMATED = "ESTIMATED"       # Heuristically estimated (e.g. speed, estimated capacity)
    PREDICTED = "PREDICTED"       # Temporal/spatial extrapolation (e.g. smoke propagation, blockage)


class SpatialRegionType(str, Enum):
    """Categorization of floorplan regions and architectural spaces."""
    ROOM = "ROOM"
    CORRIDOR = "CORRIDOR"
    HALL = "HALL"
    LOBBY = "LOBBY"
    STAIRWELL = "STAIRWELL"
    ELEVATOR = "ELEVATOR"
    DOOR = "DOOR"
    EXIT = "EXIT"
    RESTRICTED = "RESTRICTED"
    HAZARD_ZONE = "HAZARD_ZONE"
    UNKNOWN = "UNKNOWN"

