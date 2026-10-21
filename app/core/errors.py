"""
Domain and system error hierarchy for PHOENIX.
"""

from typing import Any, Optional


class PhoenixError(Exception):
    """Base exception for all PHOENIX errors."""

    def __init__(self, message: str, details: Optional[dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.message = message
        self.details = details or {}


class DomainError(PhoenixError):
    """Base error for domain and business logic violations."""
    pass


class InvalidCalibrationError(DomainError):
    """Raised when a camera calibration matrix is invalid, missing, or has insufficient points."""
    pass


class SpatialMappingUnavailableError(DomainError):
    """Raised when homography mapping fails or is unavailable for a camera."""
    pass


class ModelUnavailableError(DomainError):
    """Raised when the AI / YOLO perception model is unavailable, unloaded, or corrupted."""
    pass


class NoValidRouteError(DomainError):
    """Raised when no passable evacuation path exists from origin to any exit."""
    pass


class NoValidExitError(DomainError):
    """Raised when all building exits are blocked or unavailable."""
    pass


class PersistenceUnavailableError(DomainError):
    """Raised when database operations fail or SQLite transaction cannot be committed."""
    pass


class UnauthorizedError(DomainError):
    """Raised when an action is attempted without valid authentication or authorization."""
    pass


class ForbiddenError(DomainError):
    """Raised when an authenticated user lacks permissions or attempts cross-tenant access."""
    pass


class CameraNotFoundError(DomainError):
    """Raised when a referenced camera ID does not exist."""
    pass


class CameraOfflineError(DomainError):
    """Raised when an operation requires an active camera that is currently offline."""
    pass


class IncidentNotFoundError(DomainError):
    """Raised when a requested incident ID cannot be found."""
    pass


class BuildingNotFoundError(DomainError):
    """Raised when a requested building or floor cannot be found."""
    pass


class GraphDisconnectedError(DomainError):
    """Raised when the navigation graph structure has disconnected components."""
    pass


class StaleDataError(DomainError):
    """Raised when perception or risk data exceeds the freshness threshold."""
    pass
