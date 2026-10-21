"""
Abstract Port Interfaces for PHOENIX.
Defines contracts for perception, spatial mapping, decision intelligence, persistence, and realtime events.
"""

from abc import ABC, abstractmethod
from typing import Any, Optional
import numpy as np

from app.domain.events import DomainEvent
from app.domain.models import (
    AuditEvent,
    Building,
    Calibration,
    Camera,
    Detection,
    Floor,
    Incident,
    NavigationEdge,
    NavigationNode,
    Point2D,
    RiskSnapshot,
    RouteRecommendation,
    SmokeObservation,
    User,
)


class FrameSource(ABC):
    """Port for video and frame ingestion (e.g. MP4 video file, RTSP stream, webcam)."""

    @abstractmethod
    def read_frame(self) -> tuple[bool, Optional[np.ndarray], float]:
        """
        Read the next video frame.
        Returns: (success: bool, frame: Optional[np.ndarray], timestamp_seconds: float)
        """
        pass

    @abstractmethod
    def is_opened(self) -> bool:
        """Check if video source is currently accessible."""
        pass

    @abstractmethod
    def release(self) -> None:
        """Release video source handle and resources."""
        pass


class Detector(ABC):
    """Port for deep learning perception models (e.g. YOLOv11)."""

    @abstractmethod
    def detect(self, frame: np.ndarray, frame_id: str, camera_id: str, timestamp_seconds: float) -> list[Detection]:
        """Perform object detection on a single frame and return structured detections."""
        pass

    @abstractmethod
    def is_ready(self) -> bool:
        """Check if the model is loaded and ready for inference."""
        pass

    @abstractmethod
    def get_supported_classes(self) -> list[str]:
        """Return list of supported detection class names."""
        pass


class SpatialMapper(ABC):
    """Port for geometric camera calibration and coordinate projection."""

    @abstractmethod
    def image_to_floorplan(self, point: Point2D, calibration: Calibration) -> Point2D:
        """Transform image pixel coordinates to floorplan metric coordinates using homography."""
        pass

    @abstractmethod
    def compute_calibration_matrix(self, points: list[Any]) -> list[list[float]]:
        """Calculate 3x3 homography matrix from 4+ corresponding point pairs."""
        pass

    @abstractmethod
    def validate_calibration(self, calibration: Calibration) -> bool:
        """Validate homography matrix numerical stability and reprojection error."""
        pass


class TemporalAnalyzer(ABC):
    """Port for multi-frame temporal smoke tracking and growth rate computation."""

    @abstractmethod
    def process_observations(
        self,
        camera_id: str,
        detections: list[Detection],
        timestamp_seconds: float,
    ) -> Optional[SmokeObservation]:
        """Update smoke history buffer and calculate smoke-region growth rate."""
        pass

    @abstractmethod
    def reset_camera_history(self, camera_id: str) -> None:
        """Clear historical tracking buffer for a given camera."""
        pass


class RiskEngine(ABC):
    """Port for deterministic spatial risk evaluation."""

    @abstractmethod
    def calculate_risk(
        self,
        building_id: str,
        floor_id: str,
        nodes: list[NavigationNode],
        detections: list[Detection],
        smoke_observations: list[SmokeObservation],
    ) -> RiskSnapshot:
        """Compute deterministic risk scores for all navigation nodes."""
        pass


class OccupancyEstimator(ABC):
    """Port for estimating approximate zone/corridor headcount from person detections."""

    @abstractmethod
    def estimate_node_occupancies(
        self,
        nodes: list[NavigationNode],
        person_detections: list[Detection],
    ) -> dict[str, int]:
        """Return approximate occupant count mapped to each navigation node."""
        pass


class PredictionEngine(ABC):
    """Port for evaluating potential corridor blockage based on temporal growth and proximity."""

    @abstractmethod
    def predict_blockage_scores(
        self,
        edges: list[NavigationEdge],
        nodes_dict: dict[str, NavigationNode],
        smoke_observations: list[SmokeObservation],
    ) -> dict[str, float]:
        """Compute predicted blockage scores in [0.0, 1.0] for each navigation edge."""
        pass


class RoutingEngine(ABC):
    """Port for deterministic evacuation route computation via graph algorithms."""

    @abstractmethod
    def compute_route(
        self,
        nodes: list[NavigationNode],
        edges: list[NavigationEdge],
        origin_node_id: str,
        destination_exit_ids: list[str],
        risk_snapshot: Optional[RiskSnapshot] = None,
        occupancy_map: Optional[dict[str, int]] = None,
        blockage_predictions: Optional[dict[str, float]] = None,
    ) -> RouteRecommendation:
        """Compute deterministic evacuation path with explicit cost reason breakdown."""
        pass


class ETAEstimator(ABC):
    """Port for deterministic estimated travel time calculation."""

    @abstractmethod
    def calculate_eta(
        self,
        path_nodes: list[NavigationNode],
        path_edges: list[NavigationEdge],
        occupancy_map: Optional[dict[str, int]] = None,
        risk_snapshot: Optional[RiskSnapshot] = None,
    ) -> float:
        """Calculate estimated evacuation time in seconds under configured assumptions."""
        pass


class EventPublisher(ABC):
    """Port for publishing domain events to persistence and WebSocket channels."""

    @abstractmethod
    async def publish(self, event: DomainEvent) -> None:
        """Publish a domain event asynchronously to all subscribers."""
        pass


class BuildingRepository(ABC):
    """Repository port for building and floor persistence."""

    @abstractmethod
    def get_building(self, building_id: str) -> Optional[Building]:
        pass

    @abstractmethod
    def get_floor_nodes(self, building_id: str, floor_id: str) -> list[NavigationNode]:
        pass

    @abstractmethod
    def get_floor_edges(self, building_id: str, floor_id: str) -> list[NavigationEdge]:
        pass


class CameraRepository(ABC):
    """Repository port for camera and calibration persistence."""

    @abstractmethod
    def get_camera(self, camera_id: str) -> Optional[Camera]:
        pass

    @abstractmethod
    def get_cameras_by_floor(self, building_id: str, floor_id: str) -> list[Camera]:
        pass

    @abstractmethod
    def update_camera_status(self, camera_id: str, status: str) -> None:
        pass


class IncidentRepository(ABC):
    """Repository port for emergency incidents."""

    @abstractmethod
    def get_current_active_incident(self, building_id: str) -> Optional[Incident]:
        pass

    @abstractmethod
    def save_incident(self, incident: Incident) -> None:
        pass


class AuditRepository(ABC):
    """Repository port for audit events."""

    @abstractmethod
    def record_audit_event(self, event: AuditEvent) -> None:
        pass


class UserRepository(ABC):
    """Repository port for user authentication and authorization."""

    @abstractmethod
    def get_user_by_email(self, email: str) -> Optional[User]:
        pass

    @abstractmethod
    def get_user_by_id(self, user_id: str) -> Optional[User]:
        pass
