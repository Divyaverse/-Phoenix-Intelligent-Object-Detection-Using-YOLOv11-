"""
Homography and spatial projection transformations for camera-to-floorplan mapping.
"""

from typing import Optional
import cv2
import numpy as np

from app.core.config import SpatialConfig, settings
from app.core.errors import InvalidCalibrationError, SpatialMappingUnavailableError
from app.domain.interfaces import SpatialMapper
from app.domain.models import Calibration, CalibrationPoint, Point2D


class PlanarHomographyMapper(SpatialMapper):
    """
    Computes and applies 2D planar homography matrices to map camera image pixel coordinates
    to physical metric floorplan coordinates.
    """

    def __init__(self, config: Optional[SpatialConfig] = None) -> None:
        self.config = config or settings.spatial

    def compute_calibration_matrix(self, points: list[CalibrationPoint]) -> tuple[list[list[float]], float]:
        """
        Compute 3x3 homography matrix from at least 4 corresponding point pairs.
        Returns: (matrix_3x3, reprojection_error)
        """
        if len(points) < self.config.min_calibration_points:
            raise InvalidCalibrationError(
                f"Insufficient calibration points: provided {len(points)}, required minimum is {self.config.min_calibration_points}",
                details={"provided_points_count": len(points)},
            )

        src_pts = np.array([[p.image_point.x, p.image_point.y] for p in points], dtype=np.float32)
        dst_pts = np.array([[p.floor_point.x, p.floor_point.y] for p in points], dtype=np.float32)

        # Compute Homography matrix using RANSAC
        H, mask = cv2.findHomography(src_pts, dst_pts, cv2.RANSAC, 5.0)

        if H is None or H.shape != (3, 3):
            raise InvalidCalibrationError(
                "Failed to compute valid homography matrix (points may be collinear or degenerate)"
            )

        # Check matrix determinant (non-singular)
        det = float(np.linalg.det(H))
        if abs(det) < 1e-8 or np.isnan(det):
            raise InvalidCalibrationError("Computed homography matrix is singular or numerically unstable")

        # Normalize matrix so H[2,2] == 1.0 if non-zero
        if abs(H[2, 2]) > 1e-8:
            H = H / H[2, 2]

        # Calculate mean reprojection error
        reprojected = cv2.perspectiveTransform(src_pts.reshape(-1, 1, 2), H).reshape(-1, 2)
        errors = np.linalg.norm(dst_pts - reprojected, axis=1)
        mean_error = float(np.mean(errors))

        if mean_error > self.config.reprojection_error_threshold:
            raise InvalidCalibrationError(
                f"Calibration reprojection error ({mean_error:.2f}) exceeds maximum threshold ({self.config.reprojection_error_threshold:.2f})",
                details={"reprojection_error": mean_error},
            )

        matrix_list = H.tolist()
        return matrix_list, round(mean_error, 3)

    def image_to_floorplan(self, point: Point2D, calibration: Calibration) -> Point2D:
        """
        Project image pixel point to floorplan metric coordinates.
        """
        if not calibration.is_valid:
            raise SpatialMappingUnavailableError(
                f"Calibration for camera {calibration.camera_id} is marked invalid",
                details={"camera_id": calibration.camera_id},
            )

        if not calibration.matrix_3x3 or len(calibration.matrix_3x3) != 3:
            raise InvalidCalibrationError(
                f"Calibration matrix for camera {calibration.camera_id} is missing or malformed"
            )

        H = np.array(calibration.matrix_3x3, dtype=np.float64)

        # Homogeneous coordinate transform: [x', y', w']^T = H * [u, v, 1]^T
        img_vec = np.array([point.x, point.y, 1.0], dtype=np.float64)
        floor_vec = H @ img_vec

        w = floor_vec[2]
        if abs(w) < 1e-6 or np.isnan(w):
            raise SpatialMappingUnavailableError(
                "Homography projection singularity (division by zero scale factor)"
            )

        floor_x = float(floor_vec[0] / w)
        floor_y = float(floor_vec[1] / w)

        if np.isnan(floor_x) or np.isnan(floor_y) or np.isinf(floor_x) or np.isinf(floor_y):
            raise SpatialMappingUnavailableError("Homography produced non-finite coordinates")

        return Point2D(x=round(floor_x, 3), y=round(floor_y, 3))

    def validate_calibration(self, calibration: Calibration) -> bool:
        """Check if calibration matrix is numerically valid and non-degenerate."""
        if not calibration.matrix_3x3 or len(calibration.matrix_3x3) != 3:
            return False
        try:
            H = np.array(calibration.matrix_3x3, dtype=np.float64)
            det = float(np.linalg.det(H))
            return not (np.isnan(det) or abs(det) < 1e-8)
        except Exception:
            return False
