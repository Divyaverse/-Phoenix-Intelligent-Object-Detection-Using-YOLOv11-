"""
Unit tests for PHOENIX domain error hierarchy.
"""

import pytest
from app.core.errors import (
    CameraOfflineError,
    DomainError,
    InvalidCalibrationError,
    ModelUnavailableError,
    NoValidExitError,
    NoValidRouteError,
    PersistenceUnavailableError,
    PhoenixError,
    SpatialMappingUnavailableError,
    UnauthorizedError,
)


def test_error_hierarchy():
    """Verify all domain errors inherit properly from DomainError and PhoenixError."""
    err = InvalidCalibrationError("Calibration points insufficient", details={"camera_id": "cam_01"})
    assert isinstance(err, DomainError)
    assert isinstance(err, PhoenixError)
    assert err.message == "Calibration points insufficient"
    assert err.details["camera_id"] == "cam_01"


def test_specific_failure_errors():
    """Verify distinct error types can be raised and caught distinctly."""
    with pytest.raises(ModelUnavailableError):
        raise ModelUnavailableError("YOLO weights not found at path")

    with pytest.raises(NoValidRouteError):
        raise NoValidRouteError("All candidate paths exceed blocked hazard threshold")

    with pytest.raises(PersistenceUnavailableError):
        raise PersistenceUnavailableError("SQLite lock acquisition timed out")
