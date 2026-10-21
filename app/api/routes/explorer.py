"""
Data & Storage Explorer API Routes for PHOENIX.
Provides secure, authorized, read-only system storage inspection,
database schema discovery, safe user metadata inventory,
paginated processing-job explorer, and exportable reviewer report.
"""

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import re
from typing import Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import JSONResponse

from app.api.dependencies import get_current_user_payload, require_role
from app.core.config import settings
from app.db.sqlite import db_transaction, get_db_path
from app.domain.enums import UserRole

router = APIRouter(prefix="/explorer", tags=["Data & Storage Explorer"])


def _get_dir_stats(dir_path: Path) -> dict[str, Any]:
    """Inspect directory existence, file count, and aggregate size."""
    resolved = dir_path.resolve()
    if not resolved.exists() or not resolved.is_dir():
        return {
            "path": str(resolved),
            "exists": False,
            "file_count": 0,
            "total_size_bytes": 0,
            "last_modified": None,
        }
    
    file_count = 0
    total_size = 0
    latest_mtime = 0.0
    try:
        for root, _, files in os.walk(resolved):
            for f in files:
                fp = Path(root) / f
                try:
                    stat = fp.stat()
                    file_count += 1
                    total_size += stat.st_size
                    if stat.st_mtime > latest_mtime:
                        latest_mtime = stat.st_mtime
                except (OSError, PermissionError):
                    continue
    except (OSError, PermissionError):
        pass

    return {
        "path": str(resolved),
        "exists": True,
        "file_count": file_count,
        "total_size_bytes": total_size,
        "last_modified": datetime.fromtimestamp(latest_mtime, tz=timezone.utc).isoformat() if latest_mtime > 0 else None,
    }


def _get_file_stats(file_path: Path) -> dict[str, Any]:
    """Inspect individual file existence, size, and modified timestamp."""
    resolved = file_path.resolve()
    if not resolved.exists() or not resolved.is_file():
        return {
            "path": str(resolved),
            "exists": False,
            "size_bytes": 0,
            "last_modified": None,
        }
    try:
        stat = resolved.stat()
        return {
            "path": str(resolved),
            "exists": True,
            "size_bytes": stat.st_size,
            "last_modified": datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc).isoformat(),
        }
    except (OSError, PermissionError):
        return {
            "path": str(resolved),
            "exists": False,
            "size_bytes": 0,
            "last_modified": None,
        }


@router.get("/overview")
def get_storage_overview(
    payload: dict = Depends(require_role([UserRole.SUPERADMIN, UserRole.BUILDING_MANAGER, UserRole.FIRST_RESPONDER])),
) -> dict[str, Any]:
    """
    Retrieve real configured storage locations, file existence status, sizes,
    and checkpoint integrity for authorized reviewers.
    """
    db_file = Path(get_db_path())
    db_stats = _get_file_stats(db_file)

    # Inspect SQLite Journal mode
    journal_mode = "UNKNOWN"
    try:
        with db_transaction() as conn:
            row = conn.execute("PRAGMA journal_mode;").fetchone()
            if row:
                journal_mode = str(row[0]).upper()
    except Exception:
        pass

    db_stats["journal_mode"] = journal_mode
    db_stats["database_type"] = "SQLite 3 (WAL mode)"

    storage_dirs = {
        "uploaded_source_videos": _get_dir_stats(Path("storage/videos")),
        "perception_job_artifacts": _get_dir_stats(Path("storage/jobs")),
        "default_cctv_demonstration_videos": _get_dir_stats(Path("videos")),
        "yolo_model_checkpoints": _get_dir_stats(Path("models")),
    }

    key_artifacts = {
        "fire_smoke_checkpoint": _get_file_stats(Path("models/fire_smoke_best.pt")),
        "person_headcount_checkpoint": _get_file_stats(Path("models/yolo11n.pt")),
        "default_cctv_raw_video": _get_file_stats(Path("videos/Main_video.mp4")),
        "default_cctv_annotated_video": _get_file_stats(Path("videos/Main_video_annotated.mp4")),
    }

    return {
        "audit_timestamp": datetime.now(timezone.utc).isoformat(),
        "database": db_stats,
        "directories": storage_dirs,
        "key_artifacts": key_artifacts,
        "authenticated_reviewer": {
            "user_id": payload.get("sub"),
            "role": payload.get("role"),
            "organization_id": payload.get("org_id"),
        },
    }


@router.get("/users")
def get_user_inventory(
    payload: dict = Depends(require_role([UserRole.SUPERADMIN, UserRole.BUILDING_MANAGER])),
) -> dict[str, Any]:
    """
    Display safe user metadata and account inventory.
    Strictly excludes password hashes, secrets, and auth tokens.
    """
    user_role = payload.get("role")
    org_id = payload.get("org_id")

    sql = """
    SELECT user_id, organization_id, email, full_name, role, is_active, created_at, updated_at
    FROM users
    """
    params = ()
    # Building managers only see users within their organization
    if user_role == UserRole.BUILDING_MANAGER.value and org_id:
        sql += " WHERE organization_id = ?"
        params = (org_id,)

    sql += " ORDER BY created_at ASC;"

    users_list = []
    with db_transaction() as conn:
        rows = conn.execute(sql, params).fetchall()
        for r in rows:
            users_list.append({
                "user_id": r["user_id"],
                "organization_id": r["organization_id"],
                "email": r["email"],
                "full_name": r["full_name"],
                "role": r["role"],
                "is_active": bool(r["is_active"]),
                "created_at": r["created_at"],
                "updated_at": r["updated_at"],
            })

    return {
        "total_users": len(users_list),
        "users": users_list,
        "identity_architecture_explanation": {
            "user_id": "Unique persistent identifier assigned to an operator account (e.g. 'usr-admin-01').",
            "role": "Cryptographically enforced role that determines backend RBAC permissions (e.g. 'SUPERADMIN').",
            "access_token": "Short-lived signed JWT bearer credential used to authorize API calls over HTTP and WebSocket.",
            "storage_security": "Passwords are never stored in plaintext; all credentials are secure Argon2id cryptographic hashes.",
        },
    }


@router.get("/database")
def get_database_inventory(
    payload: dict = Depends(require_role([UserRole.SUPERADMIN, UserRole.BUILDING_MANAGER])),
) -> dict[str, Any]:
    """
    Discover existing tables, row counts, primary keys, and architectural purposes.
    Uses read-only queries with parameterized safety.
    """
    table_metadata = {
        "users": ("user_id", "User credentials, Argon2id hashes, roles, and status"),
        "auth_sessions": ("session_id", "Revocable active and historical refresh token sessions"),
        "organizations": ("organization_id", "Multi-tenant tenant partition records"),
        "buildings": ("building_id", "Facility structures, addresses, and physical metadata"),
        "floors": ("floor_id", "Building floor dimensions, scale references, and levels"),
        "cameras": ("camera_id", "Monitored CCTV cameras, streams, and calibration linkages"),
        "calibrations": ("calibration_id", "3x3 planar homography transformation matrices for cameras"),
        "floorplans": ("floorplan_id", "Floorplan blueprint dimensions, walls, exits, and navigation graphs"),
        "video_sources": ("video_id", "Ingested source video files, SHA-256 checksums, and storage paths"),
        "processing_jobs": ("job_id", "Background YOLO perception processing jobs and status"),
        "video_frames": ("frame_id", "Sampled video frames, hazard flags, and keyframe paths"),
        "detections": ("detection_id", "YOLOv11 bounding boxes, classes (fire/smoke/person), and confidences"),
        "temporal_analyses": ("analysis_id", "2D smoke plume surface areas, growth rates, and trends"),
        "risk_events": ("snapshot_id", "Spatial hazard levels and per-node risk scores"),
        "incidents": ("incident_id", "Confirmed active and resolved emergency incidents"),
        "route_recommendations": ("route_id", "Multi-factor Dijkstra shortest evacuation routes and ETAs"),
        "audit_events": ("audit_id", "Tamper-evident append-only system audit log"),
    }

    tables_inventory = []
    total_rows_across_db = 0

    with db_transaction() as conn:
        # Get actual table names from sqlite_master
        existing_tables_rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%';"
        ).fetchall()
        existing_tables = {r[0] for r in existing_tables_rows}

        for tbl_name, (pk, desc) in table_metadata.items():
            if tbl_name in existing_tables:
                cnt = conn.execute(f"SELECT COUNT(*) FROM [{tbl_name}];").fetchone()[0]
                total_rows_across_db += cnt
                tables_inventory.append({
                    "table_name": tbl_name,
                    "exists": True,
                    "row_count": cnt,
                    "primary_key": pk,
                    "description": desc,
                })
            else:
                tables_inventory.append({
                    "table_name": tbl_name,
                    "exists": False,
                    "row_count": 0,
                    "primary_key": pk,
                    "description": desc,
                })

    return {
        "database_file": get_db_path(),
        "total_tables": len(tables_inventory),
        "total_records": total_rows_across_db,
        "tables": tables_inventory,
    }


@router.get("/jobs")
def get_jobs_inventory(
    limit: int = Query(25, ge=1, le=100),
    offset: int = Query(0, ge=0),
    status_filter: Optional[str] = Query(None, alias="status"),
    payload: dict = Depends(require_role([UserRole.SUPERADMIN, UserRole.BUILDING_MANAGER, UserRole.FIRST_RESPONDER])),
) -> dict[str, Any]:
    """
    Paginated processing-job and video inventory showing actual execution metrics,
    detection counts, and annotated output existence.
    """
    sql = """
    SELECT 
        j.job_id, j.video_id, j.camera_id, j.building_id, j.floor_id, j.status,
        j.progress_percent, j.current_stage, j.frames_processed, j.total_frames,
        j.detections_count, j.fire_detected, j.smoke_detected, j.max_risk_level,
        j.execution_time_seconds, j.annotated_video_path, j.created_at, j.completed_at,
        v.original_filename, v.file_size_bytes, v.sha256_checksum, v.storage_path as source_storage_path
    FROM processing_jobs j
    LEFT JOIN video_sources v ON j.video_id = v.video_id
    """
    params = []
    if status_filter:
        sql += " WHERE j.status = ?"
        params.append(status_filter.upper())

    sql += " ORDER BY j.created_at DESC LIMIT ? OFFSET ?;"
    params.extend([limit, offset])

    jobs_list = []
    with db_transaction() as conn:
        # Total count query
        count_sql = "SELECT COUNT(*) FROM processing_jobs"
        count_params = []
        if status_filter:
            count_sql += " WHERE status = ?"
            count_params.append(status_filter.upper())
        total_count = conn.execute(count_sql, count_params).fetchone()[0]

        rows = conn.execute(sql, params).fetchall()
        for r in rows:
            annotated_path = r["annotated_video_path"]
            annotated_exists = bool(annotated_path and Path(annotated_path).is_file())
            source_exists = bool(r["source_storage_path"] and Path(r["source_storage_path"]).is_file())

            jobs_list.append({
                "job_id": r["job_id"],
                "video_id": r["video_id"],
                "camera_id": r["camera_id"],
                "original_filename": r["original_filename"] or "Unknown Video",
                "file_size_bytes": r["file_size_bytes"],
                "sha256_checksum": r["sha256_checksum"],
                "source_exists": source_exists,
                "status": r["status"],
                "progress_percent": r["progress_percent"],
                "current_stage": r["current_stage"],
                "frames_processed": r["frames_processed"],
                "total_frames": r["total_frames"],
                "detections_count": r["detections_count"],
                "fire_detected": bool(r["fire_detected"]),
                "smoke_detected": bool(r["smoke_detected"]),
                "max_risk_level": r["max_risk_level"],
                "execution_time_seconds": r["execution_time_seconds"],
                "annotated_video_path": annotated_path,
                "annotated_video_exists": annotated_exists,
                "created_at": r["created_at"],
                "completed_at": r["completed_at"],
            })

    return {
        "total_jobs": total_count,
        "limit": limit,
        "offset": offset,
        "jobs": jobs_list,
    }


@router.get("/jobs/{job_id}/sample")
def get_job_sample_records(
    job_id: str,
    payload: dict = Depends(require_role([UserRole.SUPERADMIN, UserRole.BUILDING_MANAGER, UserRole.FIRST_RESPONDER])),
) -> dict[str, Any]:
    """
    Retrieve an isolated read-only sample (up to 10 rows) of detections, temporal observations,
    and route recommendations for verification without loading thousands of rows.
    Strictly validates job_id to prevent injection.
    """
    if not re.match(r"^[a-zA-Z0-9_\-]+$", job_id):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid job ID format.")

    sample_detections = []
    sample_temporal = []
    sample_routes = []
    job_info = None

    with db_transaction() as conn:
        job_row = conn.execute(
            "SELECT job_id, video_id, camera_id, status, frames_processed, detections_count, fire_detected, smoke_detected FROM processing_jobs WHERE job_id = ?;",
            (job_id,),
        ).fetchone()
        if not job_row:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Job {job_id} not found.")

        job_info = dict(job_row)

        # Detections sample
        det_rows = conn.execute(
            "SELECT detection_id, frame_id, class_name, confidence, bbox_json, floor_point_json, timestamp FROM detections WHERE job_id = ? ORDER BY rowid ASC LIMIT 10;",
            (job_id,),
        ).fetchall()
        for d in det_rows:
            bbox = json.loads(d["bbox_json"]) if d["bbox_json"] else None
            floor_pt = json.loads(d["floor_point_json"]) if d["floor_point_json"] else None
            sample_detections.append({
                "detection_id": d["detection_id"],
                "frame_id": d["frame_id"],
                "class_name": d["class_name"],
                "confidence": d["confidence"],
                "bbox": bbox,
                "floor_point": floor_pt,
                "timestamp": d["timestamp"],
            })

        # Temporal sample
        tmp_rows = conn.execute(
            "SELECT analysis_id, timestamp, area_px2, growth_rate_px2_per_sec, trend, confidence FROM temporal_analyses WHERE job_id = ? ORDER BY rowid ASC LIMIT 10;",
            (job_id,),
        ).fetchall()
        for t in tmp_rows:
            sample_temporal.append({
                "analysis_id": t["analysis_id"],
                "timestamp": t["timestamp"],
                "area_px2": t["area_px2"],
                "growth_rate_px2_per_sec": t["growth_rate_px2_per_sec"],
                "trend": t["trend"],
                "confidence": t["confidence"],
            })

        # Route sample
        rt_rows = conn.execute(
            "SELECT route_id, origin_node, destination_node, path_nodes_json, eta_seconds, total_cost, algorithm_version, computed_at FROM route_recommendations WHERE job_id = ? ORDER BY rowid ASC LIMIT 5;",
            (job_id,),
        ).fetchall()
        for r in rt_rows:
            sample_routes.append({
                "route_id": r["route_id"],
                "origin_node": r["origin_node"],
                "destination_node": r["destination_node"],
                "path_nodes": json.loads(r["path_nodes_json"]) if r["path_nodes_json"] else [],
                "eta_seconds": r["eta_seconds"],
                "total_cost": r["total_cost"],
                "algorithm_version": r["algorithm_version"],
                "computed_at": r["computed_at"],
            })

    return {
        "job": job_info,
        "sample_detections": sample_detections,
        "sample_temporal_analyses": sample_temporal,
        "sample_routes": sample_routes,
    }


@router.get("/export")
def export_reviewer_report(
    payload: dict = Depends(require_role([UserRole.SUPERADMIN, UserRole.BUILDING_MANAGER])),
) -> JSONResponse:
    """
    Generate an authorized, sanitized, read-only JSON export report for external project reviewers.
    Strictly excludes password hashes, session secrets, or raw token data.
    """
    overview = get_storage_overview(payload)
    db_inv = get_database_inventory(payload)
    user_inv = get_user_inventory(payload)
    jobs_inv = get_jobs_inventory(limit=50, offset=0, status_filter=None, payload=payload)

    report = {
        "report_title": "PHOENIX Project Reviewer Audit & Storage Verification Report",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "reviewer_identity": {
            "user_id": payload.get("sub"),
            "role": payload.get("role"),
            "organization_id": payload.get("org_id"),
        },
        "storage_architecture": overview,
        "database_inventory": db_inv,
        "user_accounts_summary": {
            "total_users": user_inv["total_users"],
            "accounts": [
                {
                    "user_id": u["user_id"],
                    "email": u["email"],
                    "role": u["role"],
                    "organization_id": u["organization_id"],
                    "is_active": u["is_active"],
                    "created_at": u["created_at"],
                }
                for u in user_inv["users"]
            ],
            "identity_architecture": user_inv["identity_architecture_explanation"],
        },
        "processing_jobs_summary": {
            "total_jobs": jobs_inv["total_jobs"],
            "recent_jobs": jobs_inv["jobs"],
        },
        "data_lineage_stages": [
            {"stage": 1, "name": "Video Upload & Ingestion", "implementation": "FastAPI stream chunking, SHA-256 checksum, storage in storage/videos/<id>/source.mp4"},
            {"stage": 2, "name": "Perception Processing Job", "implementation": "Asynchronous job creation in SQLite processing_jobs table with isolated job_id"},
            {"stage": 3, "name": "Dual-Model YOLOv11 Inference", "implementation": "Ultralytics YOLO (fire_smoke_best.pt for fire/smoke + yolo11n.pt for person headcount)"},
            {"stage": 4, "name": "Temporal Smoke Analysis", "implementation": "TemporalSmokeAnalyzer: observed 2D pixel area expansion tracking (Δarea / Δt) with EMA smoothing"},
            {"stage": 5, "name": "Planar Homography Projection", "implementation": "PlanarHomographyMapper: 3x3 perspective matrix mapping bounding box ground points to floorplan (meters)"},
            {"stage": 6, "name": "Deterministic Spatial Risk", "implementation": "DeterministicRiskEngine: exponential proximity decay exp(-lambda * d) across navigation nodes"},
            {"stage": 7, "name": "Multi-Factor Evacuation Routing", "implementation": "MultiFactorRoutingEngine: NetworkX shortest path combining distance, hazard, and congestion"},
            {"stage": 8, "name": "Persistence & Export", "implementation": "ACID SQLite persistence across 17 relational tables + WebSocket EventBus telemetry"},
        ],
        "known_limitations_and_demonstration_notes": [
            "Video upload inference on CPU takes ~30-60s for 10s video clips; GPU acceleration recommended for production.",
            "Occupant role is restricted from CCTV matrix and administrative explorer by security policy.",
            "Turn-by-turn text in the Occupant right-column HUD provides baseline life-safety guidance; topological route is displayed on the center SVG map.",
        ],
    }

    filename = f"phoenix_reviewer_audit_{datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')}.json"
    return JSONResponse(
        content=report,
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
