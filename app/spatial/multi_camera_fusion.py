"""
Multi-Camera Spatial Fusion & Deduplication Engine for PHOENIX.
Projects simultaneous detections from multiple cameras onto a shared floor coordinate system,
fuses overlapping observations within a spatial distance threshold, and isolates different floors.
"""

from datetime import datetime, timezone
import math
from typing import Optional
import uuid

from app.domain.enums import DetectionType, MeasurementProvenance
from app.domain.models import (
    Calibration,
    Detection,
    FloorHazardObservation,
    FloorplanModel,
    Point2D,
)
from app.spatial.floorplan_parser import FloorplanProcessor
from app.spatial.homography import PlanarHomographyMapper


class MultiCameraSpatialFusionEngine:
    """
    Fuses spatial detections from multiple cameras onto unified floorplan coordinates.
    """

    def __init__(
        self,
        fusion_spatial_threshold_meters: float = 3.5,
        homography_mapper: Optional[PlanarHomographyMapper] = None,
        floorplan_processor: Optional[FloorplanProcessor] = None,
    ) -> None:
        self.fusion_threshold = fusion_spatial_threshold_meters
        self.mapper = homography_mapper or PlanarHomographyMapper()
        self.fp_processor = floorplan_processor or FloorplanProcessor()

    def fuse_camera_detections(
        self,
        building_id: str,
        floor_id: str,
        camera_detections: list[tuple[str, list[Detection], Optional[Calibration]]],
        floorplan: Optional[FloorplanModel] = None,
    ) -> list[FloorHazardObservation]:
        """
        Process simultaneous detections from N cameras on a given floor.
        Args:
            camera_detections: list of (camera_id, detections, calibration)
        Returns:
            list[FloorHazardObservation] on shared floor coordinate system.
        """
        raw_floor_hazards: list[dict] = []

        for cam_id, dets, calib in camera_detections:
            for det in dets:
                if det.class_name not in (DetectionType.FIRE, DetectionType.SMOKE):
                    continue

                # 1. Map to floorplan coordinate system
                if calib and calib.is_valid:
                    floor_pt = self.mapper.image_to_floorplan(det.bbox.ground_point, calib)
                    prov = MeasurementProvenance.CALIBRATED.value
                elif det.floor_point is not None:
                    floor_pt = det.floor_point
                    prov = MeasurementProvenance.CALIBRATED.value
                else:
                    # Uncalibrated fallback: normalized screen point
                    floor_pt = Point2D(x=det.bbox.center.x / 100.0, y=det.bbox.center.y / 100.0)
                    prov = MeasurementProvenance.ESTIMATED.value

                # 2. Identify corresponding region/room and nearest node
                region_id = None
                nearest_node_id = None
                if floorplan:
                    reg = self.fp_processor.find_containing_region(floor_pt, floorplan)
                    region_id = reg.region_id if reg else None
                    node = self.fp_processor.find_nearest_node(floor_pt, floorplan.nodes)
                    nearest_node_id = node.node_id if node else None

                raw_floor_hazards.append({
                    "camera_id": cam_id,
                    "hazard_type": det.class_name.value,
                    "confidence": det.confidence,
                    "floor_point": floor_pt,
                    "region_id": region_id,
                    "nearest_node_id": nearest_node_id,
                    "provenance": prov,
                    "timestamp": det.timestamp,
                })

        if not raw_floor_hazards:
            return []

        # 3. Deterministic Spatial Clustering & Deduplication
        fused_clusters: list[list[dict]] = []
        for h in raw_floor_hazards:
            merged = False
            for cluster in fused_clusters:
                # Same hazard type and within spatial fusion threshold
                c_head = cluster[0]
                if c_head["hazard_type"] == h["hazard_type"]:
                    dist = math.sqrt(
                        (c_head["floor_point"].x - h["floor_point"].x) ** 2
                        + (c_head["floor_point"].y - h["floor_point"].y) ** 2
                    )
                    if dist <= self.fusion_threshold:
                        cluster.append(h)
                        merged = True
                        break
            if not merged:
                fused_clusters.append([h])

        # 4. Generate Unified FloorHazardObservations
        fused_observations: list[FloorHazardObservation] = []
        for idx, cluster in enumerate(fused_clusters):
            c_cams = list({item["camera_id"] for item in cluster})
            max_conf = max(item["confidence"] for item in cluster)

            # Confidence-weighted spatial centroid
            total_weight = sum(item["confidence"] for item in cluster)
            avg_x = sum(item["floor_point"].x * item["confidence"] for item in cluster) / total_weight
            avg_y = sum(item["floor_point"].y * item["confidence"] for item in cluster) / total_weight
            fused_point = Point2D(x=round(avg_x, 2), y=round(avg_y, 2))

            # Spatial uncertainty radius expands if multiple cameras observe variance
            if len(cluster) > 1:
                max_dev = max(
                    math.sqrt((item["floor_point"].x - avg_x) ** 2 + (item["floor_point"].y - avg_y) ** 2)
                    for item in cluster
                )
                unc_radius = round(max(1.0, max_dev), 2)
            else:
                unc_radius = 1.0

            head = cluster[0]
            obs = FloorHazardObservation(
                observation_id=f"fused_haz_{floor_id}_{idx+1}_{uuid.uuid4().hex[:6]}",
                building_id=building_id,
                floor_id=floor_id,
                camera_id=c_cams[0],
                hazard_type=head["hazard_type"],
                confidence=round(max_conf, 4),
                floor_point=fused_point,
                region_id=head["region_id"],
                nearest_node_id=head["nearest_node_id"],
                fused_from_cameras=c_cams,
                spatial_uncertainty_radius_meters=unc_radius,
                timestamp=datetime.now(timezone.utc),
                provenance=head["provenance"],
            )
            fused_observations.append(obs)

        return fused_observations
