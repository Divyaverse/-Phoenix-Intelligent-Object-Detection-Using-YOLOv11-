"""
Video Visual Geometry Extractor for PHOENIX.
Extracts spatial measurements directly from video frames: ground-contact points,
pixel areas, expansion rates, motion vectors, and perspective lines with explicit data provenance.
"""

from datetime import datetime, timezone
import math
from typing import Optional
import numpy as np

from app.domain.enums import MeasurementProvenance
from app.domain.models import (
    BoundingBox,
    Calibration,
    Detection,
    Point2D,
    VisualGeometryFeature,
)
from app.spatial.homography import PlanarHomographyMapper


class VideoGeometryExtractor:
    """
    Analyzes visual features and geometry directly within camera video frames.
    """

    def __init__(self, homography_mapper: Optional[PlanarHomographyMapper] = None) -> None:
        self.mapper = homography_mapper or PlanarHomographyMapper()
        self._prev_detections: dict[str, list[dict]] = {}  # camera_id -> list of tracked features

    def extract_frame_geometry(
        self,
        frame_id: str,
        camera_id: str,
        detections: list[Detection],
        frame_width: int = 1920,
        frame_height: int = 1080,
        timestamp_seconds: float = 0.0,
        calibration: Optional[Calibration] = None,
    ) -> list[VisualGeometryFeature]:
        """
        Extract structured visual geometry features from raw video detections.
        """
        features: list[VisualGeometryFeature] = []
        now = datetime.fromtimestamp(timestamp_seconds, tz=timezone.utc) if timestamp_seconds > 0 else datetime.now(timezone.utc)

        current_records: list[dict] = []

        for det in detections:
            bbox = det.bbox

            # 1. Representative Ground Contact Point (Bottom-Center in pixel coordinates)
            ground_pt = bbox.ground_point

            # 2. Relative Normalized Screen Position [0.0..1.0, 0.0..1.0]
            norm_x = round(float(ground_pt.x / max(1, frame_width)), 4)
            norm_y = round(float(ground_pt.y / max(1, frame_height)), 4)
            rel_screen = Point2D(x=norm_x, y=norm_y)

            # 3. Pixel Area (Calculated)
            px_area = round(float(bbox.area), 2)

            # 4. Expansion / Motion Velocity (Temporal delta from previous frame)
            velocity = 0.0
            prev_cam_features = self._prev_detections.get(camera_id, [])
            for prev in prev_cam_features:
                if prev["class"] == det.class_name.value:
                    # Calculate centroid displacement distance
                    dx = ground_pt.x - prev["point"].x
                    dy = ground_pt.y - prev["point"].y
                    dt = max(0.01, timestamp_seconds - prev["timestamp"])
                    velocity = round(math.sqrt(dx * dx + dy * dy) / dt, 2)
                    break

            # 5. Determine Data Provenance
            provenance = MeasurementProvenance.MEASURED.value
            if calibration and calibration.is_valid:
                # If camera homography exists, map to ground plane
                det.floor_point = self.mapper.image_to_floorplan(ground_pt, calibration)

            feature = VisualGeometryFeature(
                frame_id=frame_id,
                camera_id=camera_id,
                timestamp=now,
                bounding_box_pixels=bbox,
                ground_contact_pixel=ground_pt,
                relative_screen_position=rel_screen,
                hazard_pixel_area=px_area,
                expansion_velocity_px_per_sec=velocity,
                detected_class=det.class_name.value,
                confidence=round(det.confidence, 4),
                vanishing_point=Point2D(x=frame_width / 2.0, y=frame_height * 0.4),  # Standard perspective horizon
                provenance=provenance,
            )
            features.append(feature)

            current_records.append({
                "class": det.class_name.value,
                "point": ground_pt,
                "area": px_area,
                "timestamp": timestamp_seconds,
            })

        self._prev_detections[camera_id] = current_records
        return features

    def estimate_perspective_vanishing_point(
        self, corridor_lines: list[tuple[Point2D, Point2D]]
    ) -> Optional[Point2D]:
        """
        Estimate the geometric camera horizon / vanishing point from visual corridor edge lines.
        """
        if len(corridor_lines) < 2:
            return None

        # Line 1: p1 -> p2, Line 2: p3 -> p4
        p1, p2 = corridor_lines[0]
        p3, p4 = corridor_lines[1]

        denom = (p1.x - p2.x) * (p3.y - p4.y) - (p1.y - p2.y) * (p3.x - p4.x)
        if abs(denom) < 1e-5:
            return None  # Parallel lines

        t = ((p1.x - p3.x) * (p3.y - p4.y) - (p1.y - p3.y) * (p3.x - p4.x)) / denom
        vx = p1.x + t * (p2.x - p1.x)
        vy = p1.y + t * (p2.y - p1.y)

        return Point2D(x=round(vx, 2), y=round(vy, 2))
