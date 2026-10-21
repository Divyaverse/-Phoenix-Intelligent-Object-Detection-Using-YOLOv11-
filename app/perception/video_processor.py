"""
Modular Video Processor for PHOENIX.
Provides frame-by-frame dual-model YOLO inference, temporal smoke tracking,
planar homography spatial projection, deterministic risk evaluation,
NetworkX routing, and annotated video export for any uploaded or local video feed.
"""

from datetime import datetime, timezone
import json
import logging
import math
import os
import shutil
import time
from typing import Any, Optional
import cv2
import numpy as np

from app.domain.enums import DetectionType, RouteStatus
from app.domain.models import (
    Calibration,
    CalibrationPoint,
    Detection,
    NavigationGraph,
    Point2D,
)
from app.decision.eta import DeterministicETAEstimator
from app.decision.occupancy import ApproximateOccupancyEstimator
from app.decision.prediction import PredictiveBlockageEngine
from app.decision.risk import DeterministicRiskEngine
from app.decision.routing import MultiFactorRoutingEngine
from app.perception.detector import YOLOAdapter
from app.perception.temporal import TemporalSmokeAnalyzer
from app.spatial.floorplan_parser import FloorplanProcessor
from app.spatial.homography import PlanarHomographyMapper

logger = logging.getLogger("phoenix.video_processor")


class VideoBatchProcessor:
    """
    Processes video files frame-by-frame through the full PHOENIX intelligence pipeline.
    Exports annotated footage, per-frame detections, and quantitative benchmark statistics.
    """

    def __init__(
        self,
        fire_smoke_model_path: str = "models/fire_smoke_best.pt",
        person_model_path: str = "models/yolo11n.pt",
    ) -> None:
        self.detector = YOLOAdapter(
            fire_smoke_model_path=fire_smoke_model_path,
            person_model_path=person_model_path,
        )
        self.temporal_analyzer = TemporalSmokeAnalyzer()
        self.homography_mapper = PlanarHomographyMapper()
        self.risk_engine = DeterministicRiskEngine()
        self.occupancy_estimator = ApproximateOccupancyEstimator()
        self.prediction_engine = PredictiveBlockageEngine()
        self.routing_engine = MultiFactorRoutingEngine()
        self.eta_estimator = DeterministicETAEstimator()
        self.fp_processor = FloorplanProcessor()

    def get_default_calibration(self, camera_id: str, building_id: str, floor_id: str) -> Calibration:
        """Ground contact calibration on corridor floor tiles."""
        cal_points = [
            CalibrationPoint(image_point=Point2D(x=280.0, y=700.0), floor_point=Point2D(x=14.0, y=5.0)),
            CalibrationPoint(image_point=Point2D(x=820.0, y=700.0), floor_point=Point2D(x=18.0, y=5.0)),
            CalibrationPoint(image_point=Point2D(x=425.0, y=475.0), floor_point=Point2D(x=14.0, y=20.0)),
            CalibrationPoint(image_point=Point2D(x=575.0, y=475.0), floor_point=Point2D(x=18.0, y=20.0)),
        ]
        mat, err = self.homography_mapper.compute_calibration_matrix(cal_points)
        return Calibration(
            calibration_id=f"cal_{camera_id.lower()}",
            camera_id=camera_id,
            building_id=building_id,
            floor_id=floor_id,
            matrix_3x3=mat,
            reprojection_error=err,
            is_valid=True,
        )

    def process_video_file(
        self,
        video_path: str,
        camera_id: str = "CAM-MAIN-01",
        building_id: str = "bldg-hq-01",
        floor_id: str = "fl-01",
        output_annotated_path: Optional[str] = None,
        output_records_dir: Optional[str] = None,
        origin_node_id: Optional[str] = None,
    ) -> dict[str, Any]:
        """
        Execute frame-by-frame pipeline on an actual video file.
        """
        if not os.path.isfile(video_path):
            raise FileNotFoundError(f"Video file not found: {video_path}")

        # Floorplan & Navigation Graph
        floorplan = self.fp_processor.create_main_corridor_floorplan(building_id, floor_id)
        from app.graph.navigation_graph import NavigationGraph
        nav_graph = NavigationGraph.from_nodes_and_edges(
            building_id, floor_id, floorplan.nodes, floorplan.edges
        )

        calibration = self.get_default_calibration(camera_id, building_id, floor_id)
        all_nodes = nav_graph.get_all_nodes()
        all_edges = nav_graph.get_all_edges()
        nodes_dict = {n.node_id: n for n in all_nodes}

        # Determine origin node
        resolved_origin = origin_node_id or (
            "node_west_suites" if "node_west_suites" in nodes_dict else [n.node_id for n in all_nodes if not n.is_exit][0]
        )

        cap = cv2.VideoCapture(video_path)
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = cap.get(cv2.CAP_PROP_FPS) or 24.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))

        writer = None
        if output_annotated_path:
            os.makedirs(os.path.dirname(os.path.abspath(output_annotated_path)), exist_ok=True)
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(output_annotated_path, fourcc, fps, (width, height))

        frame_records = []
        class_detection_counts = {"fire": 0, "smoke": 0, "person": 0}
        class_confidence_sums = {"fire": 0.0, "smoke": 0.0, "person": 0.0}
        frame_latencies_ms = []

        start_time = time.perf_counter()

        for frame_idx in range(total_frames):
            ret, frame = cap.read()
            if not ret:
                break

            timestamp_sec = frame_idx / fps
            frame_id = f"f_{frame_idx:04d}"

            t0 = time.perf_counter()
            detections = self.detector.detect(
                frame=frame,
                frame_id=frame_id,
                camera_id=camera_id,
                timestamp_seconds=timestamp_sec,
            )
            lat_ms = (time.perf_counter() - t0) * 1000.0
            frame_latencies_ms.append(lat_ms)

            # Ground mapping
            for det in detections:
                if det.class_name in (DetectionType.FIRE, DetectionType.PERSON):
                    try:
                        fp = self.homography_mapper.image_to_floorplan(det.bbox.ground_point, calibration)
                        if 0.0 <= fp.x <= 40.0 and 0.0 <= fp.y <= 50.0:
                            det.floor_point = fp
                        else:
                            det.floor_point = None
                    except Exception:
                        det.floor_point = None
                else:
                    det.floor_point = None

                cname = det.class_name.value
                class_detection_counts[cname] = class_detection_counts.get(cname, 0) + 1
                class_confidence_sums[cname] = class_confidence_sums.get(cname, 0.0) + det.confidence

            # Temporal smoke analysis
            smoke_obs = self.temporal_analyzer.process_observations(camera_id, detections, timestamp_sec)
            smoke_obs_list = [smoke_obs] if smoke_obs else []

            # Risk, occupancy, and blockage
            risk_snap = self.risk_engine.calculate_risk(building_id, floor_id, all_nodes, detections, smoke_obs_list)
            occ_map = self.occupancy_estimator.estimate_node_occupancies(all_nodes, detections)
            blockage_map = self.prediction_engine.predict_blockage_scores(all_edges, nodes_dict, smoke_obs_list)

            # Dynamic Evacuation Route
            route = self.routing_engine.compute_route(
                nodes=all_nodes,
                edges=all_edges,
                origin_node_id=resolved_origin,
                destination_exit_ids=nav_graph.get_exit_node_ids(),
                risk_snapshot=risk_snap,
                occupancy_map=occ_map,
                blockage_predictions=blockage_map,
            )
            path_nodes = [nav_graph.get_node(nid) for nid in route.path_nodes if nav_graph.get_node(nid)]
            path_edges = [e for e in all_edges if e.edge_id in route.path_edges]
            route_eta = self.eta_estimator.calculate_eta(path_nodes, path_edges, occ_map, risk_snap)

            rec = {
                "frame_idx": frame_idx,
                "frame_id": frame_id,
                "timestamp_seconds": round(timestamp_sec, 3),
                "inference_latency_ms": round(lat_ms, 2),
                "detections": [
                    {
                        "class": d.class_name.value,
                        "confidence": round(d.confidence, 4),
                        "bbox": [round(d.bbox.x1, 1), round(d.bbox.y1, 1), round(d.bbox.x2, 1), round(d.bbox.y2, 1)],
                        "floor_point": {"x": round(d.floor_point.x, 2), "y": round(d.floor_point.y, 2)} if d.floor_point else None,
                    }
                    for d in detections
                ],
                "temporal_smoke": {
                    "area_px2": round(smoke_obs.area_px2, 1) if smoke_obs else 0.0,
                    "growth_rate_px2_per_sec": round(smoke_obs.smoothed_growth_rate or smoke_obs.growth_rate_px2_per_sec, 2) if smoke_obs else 0.0,
                    "trend": smoke_obs.trend.value if smoke_obs else "STABLE",
                } if smoke_obs else None,
                "risk_level": risk_snap.global_risk_level.value,
                "active_hazards": risk_snap.active_hazards_count,
                "recommended_exit": route.destination_node if route.status == RouteStatus.VALID else "NO_VALID_EXIT",
                "eta_seconds": round(route_eta, 2),
                "path": route.path_nodes,
            }
            frame_records.append(rec)

            if writer:
                annotated = frame.copy()
                for d in detections:
                    x1, y1, x2, y2 = int(d.bbox.x1), int(d.bbox.y1), int(d.bbox.x2), int(d.bbox.y2)
                    cname = d.class_name.value
                    color = (0, 69, 255) if cname == "fire" else ((200, 200, 200) if cname == "smoke" else (255, 180, 0))
                    cv2.rectangle(annotated, (x1, y1), (x2, y2), color, 2)
                    lbl = f"{cname.upper()} {d.confidence:.2f}"
                    if d.floor_point:
                        lbl += f" ({d.floor_point.x:.1f}m,{d.floor_point.y:.1f}m)"
                    (tw, th), _ = cv2.getTextSize(lbl, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
                    cv2.rectangle(annotated, (x1, max(0, y1 - 20)), (x1 + tw + 4, max(20, y1)), color, -1)
                    cv2.putText(annotated, lbl, (x1 + 2, max(15, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 0), 1, cv2.LINE_AA)

                cv2.rectangle(annotated, (0, 0), (width, 42), (18, 20, 26), -1)
                hdr = f"PHOENIX: {camera_id} | Frame {frame_idx:03d}/{total_frames} | {timestamp_sec:.2f}s | Infer {lat_ms:.1f}ms"
                cv2.putText(annotated, hdr, (12, 26), cv2.FONT_HERSHEY_SIMPLEX, 0.52, (240, 240, 245), 1, cv2.LINE_AA)

                cv2.rectangle(annotated, (0, height - 38), (width, height), (15, 17, 22), -1)
                guidance = f"EVAC: {' -> '.join(route.path_nodes)} | EXIT: {route.destination_node} | ETA: {route_eta:.1f}s"
                cv2.putText(annotated, guidance, (12, height - 14), cv2.FONT_HERSHEY_SIMPLEX, 0.48, (0, 230, 120), 1, cv2.LINE_AA)
                writer.write(annotated)

        cap.release()
        if writer:
            writer.release()

        total_time = time.perf_counter() - start_time
        fps_proc = total_frames / total_time if total_time > 0 else 0

        stats = {
            "video_file": video_path,
            "resolution": f"{width}x{height}",
            "video_fps": fps,
            "total_frames_processed": total_frames,
            "duration_seconds": round(total_frames / fps, 2),
            "processing_time_seconds": round(total_time, 2),
            "processing_fps": round(fps_proc, 2),
            "average_latency_ms": round(float(np.mean(frame_latencies_ms)), 2),
            "detection_counts": class_detection_counts,
            "average_confidences": {
                k: round(class_confidence_sums[k] / max(1, class_detection_counts[k]), 4)
                for k in class_detection_counts
            },
            "annotated_video_path": output_annotated_path,
        }

        if output_records_dir:
            os.makedirs(output_records_dir, exist_ok=True)
            with open(os.path.join(output_records_dir, "detections.json"), "w", encoding="utf-8") as f:
                json.dump(frame_records, f, indent=2)
            with open(os.path.join(output_records_dir, "statistics.json"), "w", encoding="utf-8") as f:
                json.dump(stats, f, indent=2)

        return stats
