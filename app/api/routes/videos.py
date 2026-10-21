"""
Video Upload, Storage Management, and Perception Processing Job Routes.
Enforces size/extension validation, SHA-256 hashing, path traversal prevention,
and full persistence of detections, temporal analysis, risk events, and routes.
"""

import asyncio
import json
import logging
import os
from pathlib import Path
import shutil
import tempfile
from typing import Any, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, File, HTTPException, Query, UploadFile, status
from fastapi.responses import FileResponse

from app.api.dependencies import get_current_active_user, get_current_user_payload, require_role
from app.api.schemas.contracts import ProcessingJobResponse, VideoSourceResponse
from app.core.config import settings
from app.db.sqlite import db_transaction
from app.domain.enums import UserRole
from app.domain.models import User
from app.services.video_service import VideoProcessingService

router = APIRouter(tags=["Videos & Perception Jobs"])
service = VideoProcessingService()


@router.post("/videos/upload", response_model=VideoSourceResponse, status_code=status.HTTP_201_CREATED)
async def upload_video(
    file: UploadFile = File(...),
    user: User = Depends(get_current_active_user),
) -> VideoSourceResponse:
    """
    Upload and securely store an original video file in managed isolated filesystem storage.
    Validates file extension, size, SHA-256 checksum, and decodability.
    """
    filename = Path(file.filename or "video.mp4").name
    # Write incoming stream to a temporary scratch file to validate before committing
    with tempfile.NamedTemporaryFile(delete=False, suffix=Path(filename).suffix) as tmp:
        tmp_path = Path(tmp.name)
        shutil.copyfileobj(file.file, tmp)

    try:
        record = service.validate_and_store_video(
            source_file_path=tmp_path,
            original_filename=filename,
            user_id=user.user_id,
            organization_id=user.organization_id,
        )
        return VideoSourceResponse(**record)
    except (ValueError, FileNotFoundError) as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))
    finally:
        if tmp_path.is_file():
            tmp_path.unlink()


@router.get("/videos", response_model=list[VideoSourceResponse])
def list_videos(
    user: User = Depends(get_current_active_user),
) -> list[VideoSourceResponse]:
    """List all registered video sources for the organization."""
    records = service.video_repo.list_all(user.organization_id)
    return [VideoSourceResponse(**r) for r in records]


@router.get("/videos/{video_id}", response_model=VideoSourceResponse)
def get_video(
    video_id: str,
    user: User = Depends(get_current_active_user),
) -> VideoSourceResponse:
    """Retrieve video metadata and storage details."""
    record = service.video_repo.get(video_id)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")
    return VideoSourceResponse(**record)


@router.get("/videos/{video_id}/stream")
def stream_video(
    video_id: str,
    user: User = Depends(get_current_active_user),
):
    """Stream original uploaded video file with authorization and path verification."""
    record = service.video_repo.get(video_id)
    if not record or not record.get("storage_path"):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video not found")

    safe_path = Path(record["storage_path"]).resolve()
    storage_base = Path("storage").resolve()
    if not str(safe_path).startswith(str(storage_base)) or not safe_path.is_file():
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Video file not found or inaccessible")

    return FileResponse(
        str(safe_path),
        media_type=record.get("mime_type", "video/mp4"),
        filename=record.get("stored_filename", "video.mp4"),
    )


@router.post("/videos/{video_id}/jobs", response_model=ProcessingJobResponse, status_code=status.HTTP_202_ACCEPTED)
async def create_and_start_processing_job(
    video_id: str,
    background_tasks: BackgroundTasks,
    building_id: str = Query("bldg-hq-01"),
    floor_id: str = Query("fl-01"),
    camera_id: str = Query("CAM-UPLOAD", description="Camera ID or CAM-UPLOAD for uncalibrated user upload"),
    stride: int = Query(2, ge=1, le=10, description="Frame processing stride"),
    user: User = Depends(get_current_active_user),
) -> ProcessingJobResponse:
    """
    Queue an automated YOLOv11 perceptual inference job for an uploaded video.
    Executes in the background and updates persistent database records and EventBus telemetry.
    """
    # Ensure camera exists in cameras table to guarantee foreign key integrity
    with db_transaction() as conn:
        cam_exists = conn.execute("SELECT 1 FROM cameras WHERE camera_id = ?", (camera_id,)).fetchone()
        if not cam_exists:
            conn.execute(
                """
                INSERT OR IGNORE INTO cameras (
                    camera_id, organization_id, building_id, floor_id, name, source_uri, status, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, 'ONLINE', datetime('now'))
                """,
                (
                    camera_id,
                    user.organization_id or "org-phoenix-main",
                    building_id,
                    floor_id,
                    f"Uploaded Stream ({camera_id})",
                    f"/videos/{video_id}",
                ),
            )

    try:
        job = service.create_job(
            video_id,
            user_id=user.user_id,
            organization_id=user.organization_id,
            camera_id=camera_id,
            building_id=building_id,
            floor_id=floor_id,
        )
    except FileNotFoundError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))

    # Run processing asynchronously via FastAPI background tasks
    async def _run_bg():
        try:
            await service.execute_job(
                job_id=job["job_id"],
                building_id=building_id,
                floor_id=floor_id,
                camera_id=camera_id,
                stride_frames=stride,
            )
        except Exception as exc:
            logging.getLogger("phoenix.video_service").error(
                f"Background processing error for job {job['job_id']}: {exc}",
                exc_info=True,
            )
            service.job_repo.fail_job(job["job_id"], str(exc), "PERCEPTION_BACKGROUND_ERROR")

    background_tasks.add_task(_run_bg)

    return ProcessingJobResponse(
        **{
            **job,
            "created_at": job["created_at"],
            "updated_at": job["created_at"],
            "output_metadata": None,
        }
    )


@router.get("/jobs", response_model=list[ProcessingJobResponse])
def list_jobs(
    video_id: Optional[str] = Query(None),
    limit: int = Query(50, ge=1, le=200),
    user: User = Depends(get_current_active_user),
) -> list[ProcessingJobResponse]:
    """List recent video processing jobs."""
    if video_id:
        jobs = service.job_repo.list_by_video(video_id)
    else:
        jobs = service.job_repo.list_recent(limit=limit)

    result = []
    for j in jobs:
        meta = json.loads(j["output_metadata_json"]) if j.get("output_metadata_json") else None
        result.append(
            ProcessingJobResponse(
                **{
                    **j,
                    "fire_detected": bool(j.get("fire_detected")),
                    "smoke_detected": bool(j.get("smoke_detected")),
                    "output_metadata": meta,
                }
            )
        )
    return result


@router.get("/jobs/{job_id}", response_model=ProcessingJobResponse)
def get_job(
    job_id: str,
    user: User = Depends(get_current_active_user),
) -> ProcessingJobResponse:
    """Retrieve processing job status, progress, and runtime metrics."""
    j = service.job_repo.get(job_id)
    if not j:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    meta = json.loads(j["output_metadata_json"]) if j.get("output_metadata_json") else None
    return ProcessingJobResponse(
        **{
            **j,
            "fire_detected": bool(j.get("fire_detected")),
            "smoke_detected": bool(j.get("smoke_detected")),
            "output_metadata": meta,
        }
    )


@router.get("/jobs/{job_id}/results")
def get_job_results(
    job_id: str,
    user: User = Depends(get_current_active_user),
) -> dict[str, Any]:
    """
    Retrieve full persisted data generated by the job:
    YOLO detections, temporal smoke growth metrics, spatial risk events, keyframe samples, and evacuation routes.
    """
    j = service.job_repo.get(job_id)
    if not j:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    detections = service.detection_repo.list_by_job(job_id)
    temporal = service.temporal_repo.list_by_job(job_id)
    risk_events = service.risk_repo.list_by_job(job_id)
    routes = service.route_repo.list_by_job(job_id)
    keyframes = service.frame_repo.list_by_job(job_id, keyframes_only=True)
    video = service.video_repo.get(j["video_id"])
    calib = service.cal_repo.get_by_camera(j.get("camera_id", "")) if j.get("camera_id") else None
    has_calibration = bool(calib and getattr(calib, "is_valid", False))

    return {
        "job_id": job_id,
        "video_id": j["video_id"],
        "camera_id": j.get("camera_id"),
        "original_filename": video.get("original_filename") if video else None,
        "status": j["status"],
        "has_calibration": has_calibration,
        "summary": {
            "frames_processed": j["frames_processed"],
            "total_detections": j["detections_count"],
            "fire_detected": bool(j["fire_detected"]),
            "smoke_detected": bool(j["smoke_detected"]),
            "max_risk_level": j["max_risk_level"],
            "execution_time_seconds": j.get("execution_time_seconds"),
            "annotated_video_path": j.get("annotated_video_path"),
        },
        "counts": {
            "detections": len(detections),
            "temporal_analyses": len(temporal),
            "risk_events": len(risk_events),
            "routes_computed": len(routes),
            "keyframes_saved": len(keyframes),
        },
        "latest_route": routes[-1].model_dump() if routes else None,
        "recent_detections": [d.model_dump() for d in detections[-50:]],
        "temporal_smoke_samples": temporal[-20:],
        "risk_history": risk_events[-20:],
        "keyframes": keyframes,
    }


@router.get("/jobs/{job_id}/annotated-video")
def download_annotated_video(
    job_id: str,
    user: User = Depends(get_current_active_user),
):
    """Securely stream or download the generated annotated video output for an authorized job."""
    j = service.job_repo.get(job_id)
    if not j:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    path_str = j.get("annotated_video_path")
    if not path_str or not os.path.isfile(path_str):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Annotated video not available or not yet completed.")

    safe_path = Path(path_str).resolve()
    # Path traversal check: must reside inside storage directory
    storage_base = Path("storage").resolve()
    if not str(safe_path).startswith(str(storage_base)):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied: invalid storage path.")

    return FileResponse(
        str(safe_path),
        media_type="video/mp4",
        filename=f"phoenix_annotated_{job_id}.mp4",
    )
