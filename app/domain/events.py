"""
Domain and realtime event definitions for PHOENIX.
"""

from datetime import datetime, timezone
from typing import Any, Optional, Union
from pydantic import BaseModel, Field
import uuid

from app.domain.enums import EventType, RiskLevel, RouteStatus


class EventScope(BaseModel):
    """Hierarchical scope defining tenant and physical boundaries for event distribution."""
    organization_id: Optional[str] = None
    building_id: Optional[str] = None
    floor_id: Optional[str] = None


class EventEnvelope(BaseModel):
    """
    Standardized event envelope delivered across internal services and WebSocket subscribers.
    Matches exact PRD section 17 specification: event_id, event_type, sequence, timestamp, scope, payload.
    """
    event_id: str = Field(default_factory=lambda: f"evt_{uuid.uuid4().hex[:12]}")
    event_type: EventType
    sequence: int = 0
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    scope: Union[EventScope, dict[str, Any]] = Field(default_factory=dict)
    payload: dict[str, Any] = Field(default_factory=dict)


class DomainEvent(EventEnvelope):
    """Alias/Subclass of EventEnvelope for internal domain events."""
    pass


class DetectionObservedPayload(BaseModel):
    camera_id: str
    detections_count: int
    has_fire: bool
    has_smoke: bool
    person_count: int


class SmokeGrowthAlertPayload(BaseModel):
    camera_id: str
    growth_rate_px2_per_sec: float
    smoothed_growth_rate: float
    trend: str
    alert_level: str


class RiskUpdatedPayload(BaseModel):
    building_id: str
    floor_id: str
    global_risk_level: RiskLevel
    affected_nodes: list[str] = Field(default_factory=list)
    active_hazards_count: int = 0


class RouteChangedPayload(BaseModel):
    route_id: str
    origin_node: str
    destination_node: str
    status: RouteStatus
    eta_seconds: float
    reason: str
    path_nodes: list[str]


class CameraStatusPayload(BaseModel):
    camera_id: str
    status: str
    last_seen_at: Optional[datetime] = None


class IncidentStatusPayload(BaseModel):
    incident_id: str
    status: str
    severity: str
    affected_nodes: list[str]
