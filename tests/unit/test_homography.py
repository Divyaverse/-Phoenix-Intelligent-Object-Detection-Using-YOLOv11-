"""
Unit tests for homography calibration, point projection, and failure modes.
"""

import pytest

from app.core.errors import InvalidCalibrationError, SpatialMappingUnavailableError
from app.domain.models import CalibrationPoint, Point2D
from app.spatial.calibration import CalibrationService
from app.spatial.homography import PlanarHomographyMapper


def test_homography_matrix_computation_and_projection():
    """Verify 4-point planar homography computation and accurate metric projection."""
    mapper = PlanarHomographyMapper()
    service = CalibrationService(mapper=mapper)

    # Setup 4 ground truth correspondences: rectangle in image (0..640, 0..480) -> floor (0..10m, 0..8m)
    points = [
        CalibrationPoint(image_point=Point2D(x=0.0, y=0.0), floor_point=Point2D(x=0.0, y=0.0)),
        CalibrationPoint(image_point=Point2D(x=640.0, y=0.0), floor_point=Point2D(x=10.0, y=0.0)),
        CalibrationPoint(image_point=Point2D(x=640.0, y=480.0), floor_point=Point2D(x=10.0, y=8.0)),
        CalibrationPoint(image_point=Point2D(x=0.0, y=480.0), floor_point=Point2D(x=0.0, y=8.0)),
    ]

    calibration = service.create_calibration(
        camera_id="cam_test_1",
        building_id="bld_1",
        floor_id="fl_1",
        points=points,
    )

    assert calibration.is_valid is True
    assert calibration.reprojection_error < 0.1

    # Project image midpoint (320, 240) -> should project to floor center (5.0, 4.0)
    img_center = Point2D(x=320.0, y=240.0)
    floor_pt = mapper.image_to_floorplan(img_center, calibration)

    assert abs(floor_pt.x - 5.0) < 0.05
    assert abs(floor_pt.y - 4.0) < 0.05


def test_homography_insufficient_points_fails():
    """Verify fewer than 4 points raises InvalidCalibrationError."""
    mapper = PlanarHomographyMapper()
    points = [
        CalibrationPoint(image_point=Point2D(x=0.0, y=0.0), floor_point=Point2D(x=0.0, y=0.0)),
        CalibrationPoint(image_point=Point2D(x=100.0, y=0.0), floor_point=Point2D(x=2.0, y=0.0)),
    ]

    with pytest.raises(InvalidCalibrationError, match="Insufficient calibration points"):
        mapper.compute_calibration_matrix(points)


def test_homography_invalid_calibration_fails():
    """Verify projection on invalid calibration raises SpatialMappingUnavailableError."""
    mapper = PlanarHomographyMapper()
    service = CalibrationService(mapper=mapper)

    points = [
        CalibrationPoint(image_point=Point2D(x=0.0, y=0.0), floor_point=Point2D(x=0.0, y=0.0)),
        CalibrationPoint(image_point=Point2D(x=640.0, y=0.0), floor_point=Point2D(x=10.0, y=0.0)),
        CalibrationPoint(image_point=Point2D(x=640.0, y=480.0), floor_point=Point2D(x=10.0, y=8.0)),
        CalibrationPoint(image_point=Point2D(x=0.0, y=480.0), floor_point=Point2D(x=0.0, y=8.0)),
    ]
    cal = service.create_calibration("cam_1", "bld_1", "fl_1", points)
    invalid_cal = service.invalidate_calibration(cal, reason="camera_moved")

    with pytest.raises(SpatialMappingUnavailableError, match="marked invalid"):
        mapper.image_to_floorplan(Point2D(x=100.0, y=100.0), invalid_cal)
