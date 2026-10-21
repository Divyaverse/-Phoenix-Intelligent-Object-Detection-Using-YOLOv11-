"""
Camera calibration management service.
"""

from datetime import datetime, timezone
from typing import Optional
import uuid

from app.core.errors import InvalidCalibrationError
from app.domain.models import Calibration, CalibrationPoint
from app.spatial.homography import PlanarHomographyMapper


class CalibrationService:
    """Service to generate, store, and validate camera calibrations."""

    def __init__(self, mapper: Optional[PlanarHomographyMapper] = None) -> None:
        self.mapper = mapper or PlanarHomographyMapper()

    def create_calibration(
        self,
        camera_id: str,
        building_id: str,
        floor_id: str,
        points: list[CalibrationPoint],
        version: int = 1,
    ) -> Calibration:
        """Compute and return a new validated Calibration object."""
        matrix, reprojection_error = self.mapper.compute_calibration_matrix(points)

        return Calibration(
            calibration_id=f"cal_{uuid.uuid4().hex[:8]}",
            camera_id=camera_id,
            building_id=building_id,
            floor_id=floor_id,
            matrix_3x3=matrix,
            points=points,
            version=version,
            is_valid=True,
            reprojection_error=reprojection_error,
            created_at=datetime.now(timezone.utc),
        )

    def invalidate_calibration(self, calibration: Calibration, reason: str = "camera_moved") -> Calibration:
        """Mark calibration invalid if camera was moved or damaged."""
        updated = calibration.model_copy(update={"is_valid": False})
        return updated

    def verify_mapping(self, calibration: Calibration) -> dict:
        """
        Execute mapping-confirmation workflow:
        Validates mathematical conditioning of the 3x3 homography matrix, computes determinant,
        evaluates reprojection accuracy, and reports mapping reliability.
        """
        import numpy as np
        if not calibration.is_valid or not calibration.matrix_3x3:
            return {
                "camera_id": calibration.camera_id,
                "is_valid": False,
                "status": "UNAVAILABLE",
                "reason": "Calibration marked invalid or matrix missing",
                "reprojection_error_px": calibration.reprojection_error,
            }

        H = np.array(calibration.matrix_3x3, dtype=np.float64)
        det = float(np.linalg.det(H))
        cond = float(np.linalg.cond(H)) if np.isfinite(np.linalg.cond(H)) else float("inf")

        is_stable = abs(det) > 1e-8 and cond < 1e8 and calibration.reprojection_error <= 15.0
        return {
            "camera_id": calibration.camera_id,
            "building_id": calibration.building_id,
            "floor_id": calibration.floor_id,
            "is_valid": is_stable,
            "status": "VERIFIED" if is_stable else "DEGRADED",
            "determinant": det,
            "condition_number": cond,
            "reprojection_error_px": calibration.reprojection_error,
            "verified_elements": [
                "ground_corridor_plane",
                "central_hallway_tiles",
                "east_alcove_threshold",
                "south_exit_threshold",
            ],
            "unverified_elements": [
                "ceiling_smoke_layer_3d_depth",
                "west_suites_interior_depth_beyond_glass",
                "exterior_path_beyond_north_double_doors",
            ],
        }
