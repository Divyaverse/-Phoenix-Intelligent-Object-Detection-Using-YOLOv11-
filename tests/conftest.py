"""
Shared pytest fixtures for PHOENIX test suites.
"""

from datetime import datetime, timezone
import pytest

from app.core.config import Settings, load_settings
from app.domain.enums import (
    CameraStatus,
    DetectionType,
    IncidentSeverity,
    IncidentStatus,
    RiskLevel,
    RouteStatus,
    SmokeGrowthTrend,
    UserRole,
)
from app.domain.models import (
    BoundingBox,
    Building,
    Calibration,
    CalibrationPoint,
    Camera,
    Detection,
    Floor,
    Incident,
    NavigationEdge,
    NavigationNode,
    Point2D,
    RiskSnapshot,
    RouteCostReason,
    RouteRecommendation,
    SmokeObservation,
    User,
)


@pytest.fixture
def test_settings() -> Settings:
    """Fixture providing clean default settings."""
    return load_settings()


@pytest.fixture
def sample_building() -> Building:
    """Fixture providing a standard test building with two floors."""
    floor1 = Floor(
        floor_id="fl_01",
        building_id="bld_test",
        floor_number=1,
        name="Ground Floor",
        width_meters=50.0,
        height_meters=30.0,
    )
    floor2 = Floor(
        floor_id="fl_02",
        building_id="bld_test",
        floor_number=2,
        name="Second Floor",
        width_meters=50.0,
        height_meters=30.0,
    )
    return Building(
        building_id="bld_test",
        organization_id="org_test",
        name="Test Innovation Center",
        address="100 Tech Blvd",
        floors=[floor1, floor2],
    )


@pytest.fixture
def sample_calibration() -> Calibration:
    """Fixture providing a valid 4-point planar homography calibration."""
    points = [
        CalibrationPoint(image_point=Point2D(x=100.0, y=100.0), floor_point=Point2D(x=0.0, y=0.0)),
        CalibrationPoint(image_point=Point2D(x=500.0, y=100.0), floor_point=Point2D(x=10.0, y=0.0)),
        CalibrationPoint(image_point=Point2D(x=500.0, y=400.0), floor_point=Point2D(x=10.0, y=8.0)),
        CalibrationPoint(image_point=Point2D(x=100.0, y=400.0), floor_point=Point2D(x=0.0, y=8.0)),
    ]
    # Simple affine / homography matrix for testing
    matrix = [
        [0.025, 0.0, -2.5],
        [0.0, 0.02667, -2.667],
        [0.0, 0.0, 1.0],
    ]
    return Calibration(
        calibration_id="cal_001",
        camera_id="cam_001",
        building_id="bld_test",
        floor_id="fl_01",
        matrix_3x3=matrix,
        points=points,
        is_valid=True,
    )


@pytest.fixture
def sample_camera(sample_calibration: Calibration) -> Camera:
    """Fixture providing an active camera."""
    return Camera(
        camera_id="cam_001",
        organization_id="org_test",
        building_id="bld_test",
        floor_id="fl_01",
        name="Corridor Camera North",
        source_uri="scenarios/video_corridor_01.mp4",
        status=CameraStatus.ONLINE,
        monitored_nodes=["node_corridor_1", "node_corridor_2"],
        calibration=sample_calibration,
        last_seen_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def sample_detections() -> list[Detection]:
    """Fixture providing structured detections."""
    return [
        Detection(
            detection_id="det_001",
            frame_id="frame_0042",
            timestamp=datetime.now(timezone.utc),
            camera_id="cam_001",
            class_name=DetectionType.SMOKE,
            confidence=0.88,
            bbox=BoundingBox(x1=150.0, y1=120.0, x2=250.0, y2=220.0),
            floor_point=Point2D(x=2.5, y=1.8),
        ),
        Detection(
            detection_id="det_002",
            frame_id="frame_0042",
            timestamp=datetime.now(timezone.utc),
            camera_id="cam_001",
            class_name=DetectionType.PERSON,
            confidence=0.92,
            bbox=BoundingBox(x1=300.0, y1=200.0, x2=340.0, y2=320.0),
            floor_point=Point2D(x=5.2, y=3.1),
        ),
    ]
