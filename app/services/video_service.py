"""
Video Ingestion, Media Storage, and End-to-End Perception Processing Service.
Manages isolated filesystem storage, SHA-256 validation, job lifecycles, and
real YOLOv11 perceptual pipeline execution with full entity persistence.
"""

from datetime import datetime, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import shutil
import time
from typing import Any, Optional
import uuid

import cv2
import numpy as np

from app.core.config import settings
from app.db.repositories import (
    SQLiteAuditEventRepository,
    SQLiteCalibrationRepository,
    SQLiteDetectionRepository,
    SQLiteFloorplanRepository,
    SQLiteProcessingJobRepository,
    SQLiteRiskEventRepository,
    SQLiteRouteRecommendationRepository,
    SQLiteTemporalAnalysisRepository,
    SQLiteVideoFrameRepository,
    SQLiteVideoSourceRepository,
)
from app.decision.eta import DeterministicETAEstimator
from app.decision.occupancy import ApproximateOccupancyEstimator
from app.decision.prediction import PredictiveBlockageEngine
from app.decision.risk import DeterministicRiskEngine
from app.decision.routing import MultiFactorRoutingEngine
from app.domain.enums import DetectionType, EventType
from app.domain.events import DomainEvent
from app.domain.models import AuditEvent, BoundingBox, Detection, Point2D
from app.events.bus import event_bus
from app.events.websocket_router import ws_manager
from app.perception.detector import YOLOAdapter
from app.perception.temporal import TemporalSmokeAnalyzer
from app.spatial.homography import PlanarHomographyMapper

logger = logging.getLogger("phoenix.video_service")

# Storage root constants
STORAGE_ROOT = Path("storage")
VIDEOS_STORAGE = STORAGE_ROOT / "videos"
JOBS_STORAGE = STORAGE_ROOT / "jobs"

ALLOWED_EXTENSIONS = {".mp4", ".avi", ".mov", ".mkv"}
MAX_FILE_SIZE_BYTES = 500 * 1024 * 1024  # 500 MB


def ensure_storage_dirs() -> None:
    VIDEOS_STORAGE.mkdir(parents=True, exist_ok=True)
    JOBS_STORAGE.mkdir(parents=True, exist_ok=True)


class VideoProcessingService:
    """Service orchestrating video file ingestion, job tracking, and perception persistence."""

    def __init__(self) -> None:
        ensure_storage_dirs()
        self.video_repo = SQLiteVideoSourceRepository()
        self.job_repo = SQLiteProcessingJobRepository()
        self.frame_repo = SQLiteVideoFrameRepository()
        self.detection_repo = SQLiteDetectionRepository()
        self.temporal_repo = SQLiteTemporalAnalysisRepository()
        self.risk_repo = SQLiteRiskEventRepository()
        self.route_repo = SQLiteRouteRecommendationRepository()
        self.floorplan_repo = SQLiteFloorplanRepository()
        self.cal_repo = SQLiteCalibrationRepository()
        self.audit_repo = SQLiteAuditEventRepository()

    def validate_and_store_video(
        self,
        source_file_path: Path,
        original_filename: str,
        user_id: Optional[str] = None,
        organization_id: str = "org-phoenix-main",
    ) -> dict[str, Any]:
        """
        Validate file extension, size, SHA-256 hash, and video integrity via OpenCV.
        Stores the video in an isolated folder: storage/videos/<video_id>/<safe_filename>.
        """
        # 1. Path traversal and extension validation
        safe_name = Path(original_filename).name
        ext = Path(safe_name).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            raise ValueError(f"Unsupported video file extension: '{ext}'. Allowed: {', '.join(ALLOWED_EXTENSIONS)}")

        if not source_file_path.is_file():
            raise FileNotFoundError(f"Source video file not found at: {source_file_path}")

        file_size = source_file_path.stat().st_size
        if file_size <= 0:
            raise ValueError("Uploaded video file is empty (0 bytes).")
        if file_size > MAX_FILE_SIZE_BYTES:
            raise ValueError(f"File exceeds maximum allowed size of {MAX_FILE_SIZE_BYTES / (1024*1024):.1f} MB.")

        # 2. SHA-256 Checksum computation
        sha256 = hashlib.sha256()
        with open(source_file_path, "rb") as f:
            for chunk in iter(lambda: f.read(65536), b""):
                sha256.update(chunk)
        checksum = sha256.hexdigest()

        # 3. Decode & integrity check with OpenCV
        cap = cv2.VideoCapture(str(source_file_path))
        if not cap.isOpened():
            raise ValueError("Corrupt or invalid video format: OpenCV cannot decode video stream.")

        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        fps = float(cap.get(cv2.CAP_PROP_FPS)) or 25.0
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = float(total_frames / fps) if fps > 0 else 0.0
        cap.release()

        if width <= 0 or height <= 0 or total_frames <= 0:
            raise ValueError("Video contains no decodable visual frames.")

        # 4. Generate unique video ID and isolated storage directory
        video_id = f"vid_{uuid.uuid4().hex[:12]}"
        dest_dir = VIDEOS_STORAGE / video_id
        dest_dir.mkdir(parents=True, exist_ok=True)
        stored_filename = f"source{ext}"
        dest_file = dest_dir / stored_filename

        # Move or copy file
        shutil.copy2(str(source_file_path), str(dest_file))

        video_record = {
            "video_id": video_id,
            "organization_id": organization_id,
            "original_filename": safe_name,
            "stored_filename": stored_filename,
            "storage_path": str(dest_file).replace("\\", "/"),
            "mime_type": "video/mp4" if ext == ".mp4" else f"video/{ext.lstrip('.')}",
            "file_size_bytes": file_size,
            "sha256_checksum": checksum,
            "duration_seconds": round(duration, 2),
            "fps": round(fps, 2),
            "width": width,
            "height": height,
            "uploaded_by_user_id": user_id,
            "status": "READY",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        self.video_repo.save(video_record)

        self.audit_repo.record_event(
            AuditEvent(
                audit_id=f"aud-video-upload-{video_id}",
                timestamp=datetime.now(timezone.utc),
                organization_id=organization_id,
                user_id=user_id or "SYSTEM",
                action="VIDEO_STORED",
                entity_type="VideoSource",
                entity_id=video_id,
                after_state={"filename": safe_name, "size": file_size, "sha256": checksum},
                reason="Video uploaded and validated",
            )
        )

        return video_record

    def create_job(
        self,
        video_id: str,
        user_id: Optional[str] = None,
        organization_id: str = "org-phoenix-main",
        camera_id: str = "CAM-UPLOAD",
        building_id: str = "bldg-hq-01",
        floor_id: str = "fl-01",
    ) -> dict[str, Any]:
        """Create a queued processing job record with an isolated workspace."""
        video = self.video_repo.get(video_id)
        if not video:
            raise FileNotFoundError(f"Video {video_id} does not exist.")

        job_id = f"job_{uuid.uuid4().hex[:12]}"
        job_dir = JOBS_STORAGE / job_id
        job_dir.mkdir(parents=True, exist_ok=True)
        (job_dir / "keyframes").mkdir(exist_ok=True)

        total_frames = int(video.get("duration_seconds", 0) * video.get("fps", 25))

        job_record = {
            "job_id": job_id,
            "video_id": video_id,
            "camera_id": camera_id,
            "building_id": building_id,
            "floor_id": floor_id,
            "organization_id": organization_id,
            "created_by_user_id": user_id,
            "status": "QUEUED",
            "progress_percent": 0.0,
            "current_stage": "INITIALIZING",
            "frames_processed": 0,
            "total_frames": total_frames,
            "detections_count": 0,
            "fire_detected": False,
            "smoke_detected": False,
            "max_risk_level": "LOW",
            "retry_count": 0,
            "started_at": None,
            "completed_at": None,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        self.job_repo.save(job_record)
        return job_record

    async def execute_job(
        self,
        job_id: str,
        building_id: str = "bldg-hq-01",
        floor_id: str = "fl-01",
        camera_id: str = "CAM-MAIN-01",
        stride_frames: int = 2,
        generate_annotated_video: bool = True,
    ) -> dict[str, Any]:
        """
        Run the genuine end-to-end YOLOv11 perceptual inference pipeline on the stored video.
        Persists detections, temporal analysis, risk events, and Dijkstra evacuation routes.
        """
        job = self.job_repo.get(job_id)
        if not job:
            raise FileNotFoundError(f"Job {job_id} not found.")

        video_id = job["video_id"]
        video = self.video_repo.get(video_id)
        if not video:
            self.job_repo.fail_job(job_id, f"Video {video_id} not found", "VIDEO_NOT_FOUND")
            return self.job_repo.get(job_id)

        video_path = video["storage_path"]
        if not os.path.isfile(video_path):
            self.job_repo.fail_job(job_id, f"Storage file missing: {video_path}", "FILE_MISSING")
            return self.job_repo.get(job_id)

        job_dir = JOBS_STORAGE / job_id
        keyframes_dir = job_dir / "keyframes"
        keyframes_dir.mkdir(parents=True, exist_ok=True)

        start_time = time.time()
        self.job_repo.save({**job, "status": "PROCESSING", "started_at": datetime.now(timezone.utc).isoformat()})

        # Load models and spatial engines
        detector = YOLOAdapter(
            fire_smoke_model_path="models/fire_smoke_best.pt",
            person_model_path="models/yolo11n.pt",
        )
        temporal_analyzer = TemporalSmokeAnalyzer()
        homography_mapper = PlanarHomographyMapper()
        risk_engine = DeterministicRiskEngine()
        occupancy_estimator = ApproximateOccupancyEstimator()
        prediction_engine = PredictiveBlockageEngine()
        routing_engine = MultiFactorRoutingEngine()
        eta_estimator = DeterministicETAEstimator()

        # Load floorplan navigation topology
        floorplan = self.floorplan_repo.get_by_floor(building_id, floor_id)
        if not floorplan:
            from app.spatial.floorplan_parser import FloorplanProcessor
            fp_proc = FloorplanProcessor()
            floorplan = fp_proc.create_main_corridor_floorplan(building_id, floor_id)
            self.floorplan_repo.save(floorplan)

        nodes = floorplan.nodes
        edges = floorplan.edges
        nodes_dict = {n.node_id: n for n in nodes}
        exit_ids = [n.node_id for n in nodes if n.is_exit]

        # Load homography calibration for camera if available
        calib = self.cal_repo.get_by_camera(camera_id) if camera_id else None

        cap = cv2.VideoCapture(video_path)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT)) or 100
        fps = float(cap.get(cv2.CAP_PROP_FPS)) or 25.0
        width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

        annotated_path = None
        writer = None
        if generate_annotated_video:
            annotated_file = job_dir / f"annotated_{video_id}.mp4"
            annotated_path = str(annotated_file).replace("\\", "/")
            fourcc = cv2.VideoWriter_fourcc(*"mp4v")
            writer = cv2.VideoWriter(str(annotated_file), fourcc, fps / stride_frames, (width, height))

        frames_processed = 0
        total_detections_count = 0
        fire_seen = False
        smoke_seen = False
        max_risk_level = "LOW"
        risk_level_rank = {"LOW": 1, "MEDIUM": 2, "HIGH": 3, "CRITICAL": 4}

        frame_idx = 0
        batch_detections: list[Detection] = []
        batch_frames: list[dict[str, Any]] = []

        try:
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break

                frame_idx += 1
                if frame_idx % stride_frames != 0:
                    continue

                ts_seconds = frame_idx / fps
                frame_id = f"f_{frame_idx:06d}"

                # 1. Genuine YOLOv11 perception
                detections = detector.detect(
                    frame=frame,
                    frame_id=frame_id,
                    camera_id=camera_id,
                    timestamp_seconds=ts_seconds,
                )

                has_hazard = False
                for d in detections:
                    d.job_id = job_id
                    d.model_version = "yolov11-dual"
                    if calib:
                        d.floor_point = homography_mapper.image_to_floorplan(d.bbox.ground_point, calib)

                    if d.class_name == DetectionType.FIRE:
                        fire_seen = True
                        has_hazard = True
                    elif d.class_name == DetectionType.SMOKE:
                        smoke_seen = True
                        has_hazard = True

                total_detections_count += len(detections)
                batch_detections.extend(detections)

                # Save keyframe image if hazard detected or every 100th frame
                keyframe_path = None
                is_keyframe = has_hazard or (frame_idx % 150 == 0)
                if is_keyframe and len(batch_frames) < 50:
                    kf_filename = f"kf_{frame_idx:06d}.jpg"
                    kf_dest = keyframes_dir / kf_filename
                    cv2.imwrite(str(kf_dest), frame)
                    keyframe_path = str(kf_dest).replace("\\", "/")

                batch_frames.append({
                    "frame_id": f"frm_{job_id}_{frame_idx}",
                    "job_id": job_id,
                    "video_id": video_id,
                    "frame_index": frame_idx,
                    "timestamp_seconds": round(ts_seconds, 3),
                    "frame_image_path": keyframe_path,
                    "detections_count": len(detections),
                    "has_hazard": has_hazard,
                    "is_keyframe": is_keyframe,
                })

                # 2. Temporal Smoke Analysis
                smoke_obs = temporal_analyzer.process_observations(camera_id, detections, ts_seconds)
                smoke_observations = [smoke_obs] if smoke_obs else []
                if smoke_obs:
                    self.temporal_repo.save({
                        "analysis_id": f"tmp_{job_id}_{frame_idx}",
                        "job_id": job_id,
                        "camera_id": camera_id,
                        "timestamp": smoke_obs.timestamp,
                        "area_px2": smoke_obs.area_px2,
                        "delta_area_px2": smoke_obs.delta_area_px2,
                        "dt_seconds": smoke_obs.dt_seconds,
                        "growth_rate_px2_per_sec": smoke_obs.growth_rate_px2_per_sec,
                        "smoothed_growth_rate": smoke_obs.smoothed_growth_rate,
                        "trend": smoke_obs.trend.value,
                        "confidence": smoke_obs.confidence,
                    })

                # 3. Spatial Risk & Dijkstra Route Computation (Only if verified calibration exists)
                if calib and getattr(calib, "is_valid", False):
                    if detections or frame_idx % 30 == 0:
                        risk_snap = risk_engine.calculate_risk(
                            building_id,
                            floor_id,
                            nodes,
                            detections,
                            smoke_observations,
                        )
                        curr_level = risk_snap.global_risk_level.value
                        if risk_level_rank.get(curr_level, 1) > risk_level_rank.get(max_risk_level, 1):
                            max_risk_level = curr_level

                        self.risk_repo.save({
                            "snapshot_id": f"rsk_{job_id}_{frame_idx}",
                            "job_id": job_id,
                            "building_id": building_id,
                            "floor_id": floor_id,
                            "timestamp": risk_snap.timestamp,
                            "global_risk_level": curr_level,
                            "node_risks": risk_snap.node_risks,
                            "active_hazards_count": risk_snap.active_hazards_count,
                        })

                        # Route optimization
                        occupancy_map = occupancy_estimator.estimate_node_occupancies(nodes, detections)
                        blockage = prediction_engine.predict_blockage_scores(edges, nodes_dict, smoke_observations)
                        origin_node = "node_west_suites" if "node_west_suites" in nodes_dict else nodes[0].node_id
                        route = routing_engine.compute_route(
                            nodes=nodes,
                            edges=edges,
                            origin_node_id=origin_node,
                            destination_exit_ids=exit_ids,
                            risk_snapshot=risk_snap,
                            occupancy_map=occupancy_map,
                            blockage_predictions=blockage,
                        )
                        route.job_id = job_id
                        route.graph_version = floorplan.graph_version
                        route.calculation_assumptions = {
                            "algorithm": "dijkstra_multi_factor",
                            "fire_detected": fire_seen,
                            "smoke_detected": smoke_seen,
                            "graph_nodes_count": len(nodes),
                            "verified_calibration": True,
                        }
                        path_nodes_list = [nodes_dict[nid] for nid in route.path_nodes if nid in nodes_dict]
                        path_edges_list = [e for e in edges if e.edge_id in route.path_edges]
                        route.eta_seconds = eta_estimator.calculate_eta(path_nodes_list, path_edges_list, occupancy_map, risk_snap)
                        self.route_repo.save(route)
                else:
                    # Uncalibrated video: derive genuine risk directly from detections without fake floor coordinates or fake routes
                    if fire_seen:
                        max_risk_level = "CRITICAL"
                    elif smoke_seen and max_risk_level not in ("CRITICAL", "HIGH"):
                        max_risk_level = "HIGH"

                    if detections or frame_idx % 30 == 0:
                        hazard_count = len([d for d in detections if d.class_name in (DetectionType.FIRE, DetectionType.SMOKE)])
                        curr_level = "CRITICAL" if any(d.class_name == DetectionType.FIRE for d in detections) else ("HIGH" if any(d.class_name == DetectionType.SMOKE for d in detections) else "LOW")
                        if risk_level_rank.get(curr_level, 1) > risk_level_rank.get(max_risk_level, 1):
                            max_risk_level = curr_level
                        self.risk_repo.save({
                            "snapshot_id": f"rsk_{job_id}_{frame_idx}",
                            "job_id": job_id,
                            "building_id": building_id,
                            "floor_id": floor_id,
                            "timestamp": datetime.fromtimestamp(ts_seconds, tz=timezone.utc),
                            "global_risk_level": curr_level,
                            "node_risks": {},
                            "active_hazards_count": hazard_count,
                        })

                # 4. Render overlay on frame for output video
                if writer:
                    annotated_frame = frame.copy()
                    for d in detections:
                        color = (0, 0, 255) if d.class_name == DetectionType.FIRE else ((128, 128, 128) if d.class_name == DetectionType.SMOKE else (0, 255, 0))
                        x1, y1, x2, y2 = int(d.bbox.x1), int(d.bbox.y1), int(d.bbox.x2), int(d.bbox.y2)
                        cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)
                        label = f"{d.class_name.value.upper()} {d.confidence:.2f}"
                        cv2.putText(annotated_frame, label, (x1, max(20, y1 - 8)), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)

                    # Status banner
                    hud_text = f"PHOENIX AI | Frame {frame_idx}/{total_frames} | Risk: {max_risk_level} | Detections: {len(detections)}"
                    cv2.putText(annotated_frame, hud_text, (20, 35), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                    writer.write(annotated_frame)

                frames_processed += 1
                progress = min(99.0, round((frame_idx / total_frames) * 100.0, 1))

                # Periodic progress update to DB and WebSocket
                if frames_processed % 15 == 0:
                    self.job_repo.update_progress(
                        job_id=job_id,
                        progress_percent=progress,
                        current_stage="RUNNING_PERCEPTION",
                        frames_processed=frames_processed,
                        detections_count=total_detections_count,
                        fire_detected=fire_seen,
                        smoke_detected=smoke_seen,
                        max_risk=max_risk_level,
                    )

            # Persist remaining batch detections and frames
            if batch_detections:
                self.detection_repo.save_batch(batch_detections)
            if batch_frames:
                self.frame_repo.save_batch(batch_frames)

            cap.release()
            if writer:
                writer.release()

            exec_time = round(time.time() - start_time, 2)

            meta = {
                "total_frames_in_video": total_frames,
                "frames_analyzed": frames_processed,
                "detections_count": total_detections_count,
                "fire_detected": fire_seen,
                "smoke_detected": smoke_seen,
                "max_risk_level": max_risk_level,
                "execution_time_seconds": exec_time,
                "model_version": "yolov11-dual (fire_smoke_best.pt + yolo11n.pt)",
                "graph_version": floorplan.graph_version,
            }

            self.job_repo.complete_job(
                job_id=job_id,
                annotated_video_path=annotated_path,
                output_metadata=meta,
                execution_time_seconds=exec_time,
            )

            # Audit completion
            self.audit_repo.record_event(
                AuditEvent(
                    audit_id=f"aud-job-comp-{job_id}",
                    timestamp=datetime.now(timezone.utc),
                    organization_id=job.get("organization_id", "org-phoenix-main"),
                    user_id=job.get("created_by_user_id") or "SYSTEM",
                    action="JOB_COMPLETED",
                    entity_type="ProcessingJob",
                    entity_id=job_id,
                    after_state=meta,
                    reason="Processing finished successfully",
                )
            )

            logger.info(f"Job {job_id} completed successfully in {exec_time}s with {total_detections_count} detections.")
            return self.job_repo.get(job_id)

        except Exception as e:
            logger.error(f"Job {job_id} failed with error: {str(e)}", exc_info=True)
            if cap and cap.isOpened():
                cap.release()
            if writer:
                writer.release()
            self.job_repo.fail_job(job_id, str(e), "PERCEPTION_PIPELINE_ERROR")
            return self.job_repo.get(job_id)
