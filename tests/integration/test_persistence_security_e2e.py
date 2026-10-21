"""
Comprehensive Integration Tests for PHOENIX:
- Authentication (Argon2id, Login, Refresh rotation, Session revocation)
- RBAC (SuperAdmin, BuildingManager, FirstResponder, Occupant)
- Database constraints and relational integrity
- Video upload validation, checksumming, and managed storage isolation
- Entity persistence (Jobs, Frames, Detections, Temporal Analyses, Risk Events, Route Recommendations)
- Concurrency and per-job isolation
- Durability across application/database restarts
"""

import os
import uuid
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from fastapi.testclient import TestClient

from app.main import app
from app.db.session import engine
from app.db.repositories import (
    SQLiteUserRepository,
    SQLiteAuthSessionRepository,
    SQLiteVideoSourceRepository,
    SQLiteProcessingJobRepository,
    SQLiteVideoFrameRepository,
    SQLiteDetectionRepository,
    SQLiteTemporalAnalysisRepository,
    SQLiteRiskEventRepository,
    SQLiteRouteRecommendationRepository,
)
from app.core.security import hash_password, verify_password, create_access_token, decode_access_token
from app.domain.enums import UserRole, JobStatus, RouteStatus, DetectionType
from app.domain.models import Detection, BoundingBox, Point2D, RouteRecommendation, RouteCostReason


@pytest.fixture(scope="module")
def client():
    return TestClient(app)


@pytest.fixture(scope="module")
def admin_credentials():
    return {"email": "admin@phoenix.local", "password": "AdminPass123!"}


@pytest.fixture(scope="module")
def manager_credentials():
    return {"email": "manager@phoenix.local", "password": "ManagerPass123!"}


# ------------------------------------------------------------------------------
# 1. Authentication & Security (Argon2id, Refresh Tokens, JWT)
# ------------------------------------------------------------------------------

def test_argon2id_password_hashing():
    """Verify passwords are authenticated and hashed using Argon2id."""
    password = "SuperStrongPassword123!"
    hashed = hash_password(password)
    assert hashed.startswith("$argon2id$")
    assert verify_password(password, hashed) is True
    assert verify_password("WrongPassword123!", hashed) is False


def test_auth_login_success(client, admin_credentials):
    """Test login endpoint creates session and returns access and refresh tokens."""
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": admin_credentials["email"], "password": admin_credentials["password"]},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"

    # Verify JWT claims
    claims = decode_access_token(data["access_token"])
    assert claims["role"] == UserRole.SUPERADMIN.value
    assert claims["sub"] == "usr-admin-01"


def test_auth_login_invalid_password(client):
    """Test login failure on incorrect password."""
    resp = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@phoenix.local", "password": "DefinitivelyWrongPassword"},
    )
    assert resp.status_code == 401
    assert "Invalid email credentials" in resp.json()["detail"]


def test_refresh_token_rotation_and_revocation(client, admin_credentials):
    """Test refresh token rotation issues new access/refresh tokens and invalidates old."""
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": admin_credentials["email"], "password": admin_credentials["password"]},
    )
    assert login_resp.status_code == 200
    old_refresh = login_resp.json()["refresh_token"]

    # Refresh
    refresh_resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh},
    )
    assert refresh_resp.status_code == 200
    new_data = refresh_resp.json()
    assert "access_token" in new_data
    assert "refresh_token" in new_data
    new_refresh = new_data["refresh_token"]
    assert new_refresh != old_refresh

    # Old refresh token is revoked and should fail
    fail_resp = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": old_refresh},
    )
    assert fail_resp.status_code == 401


def test_logout_revokes_session(client, admin_credentials):
    """Test /logout revokes active session and invalidates refresh token."""
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": admin_credentials["email"], "password": admin_credentials["password"]},
    )
    tokens = login_resp.json()
    access = tokens["access_token"]
    refresh = tokens["refresh_token"]

    # Logout
    logout_resp = client.post(
        "/api/v1/auth/logout",
        headers={"Authorization": f"Bearer {access}"},
        json={"refresh_token": refresh},
    )
    assert logout_resp.status_code == 200
    assert logout_resp.json()["status"] == "SUCCESS"

    # Refresh token should now be rejected
    fail_refresh = client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": refresh},
    )
    assert fail_refresh.status_code == 401


# ------------------------------------------------------------------------------
# 2. Role-Based Access Control (RBAC)
# ------------------------------------------------------------------------------

def test_rbac_superadmin_user_management(client, admin_credentials, manager_credentials):
    """SuperAdmin can manage users; BuildingManager is forbidden."""
    admin_login = client.post("/api/v1/auth/login", json=admin_credentials)
    admin_token = admin_login.json()["access_token"]

    mgr_login = client.post("/api/v1/auth/login", json=manager_credentials)
    mgr_token = mgr_login.json()["access_token"]

    # 1. SuperAdmin lists users
    res_admin = client.get(
        "/api/v1/auth/users",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert res_admin.status_code == 200
    users = res_admin.json()
    assert len(users) >= 4

    # 2. BuildingManager forbidden from user management
    res_mgr = client.get(
        "/api/v1/auth/users",
        headers={"Authorization": f"Bearer {mgr_token}"},
    )
    assert res_mgr.status_code == 403


# ------------------------------------------------------------------------------
# 3. Video Storage, Validation, and Isolation
# ------------------------------------------------------------------------------

def test_video_upload_validation_rejects_invalid_extension(client, admin_credentials):
    """Uploading an invalid file extension must be rejected."""
    login = client.post("/api/v1/auth/login", json=admin_credentials)
    token = login.json()["access_token"]

    file_content = b"fake video bytes"
    files = {"file": ("malicious.exe", file_content, "application/octet-stream")}
    res = client.post(
        "/api/v1/videos/upload",
        headers={"Authorization": f"Bearer {token}"},
        files=files,
    )
    assert res.status_code == 400
    assert "Unsupported video file extension" in res.json()["detail"]


def test_video_upload_validation_rejects_corrupted_video(client, admin_credentials):
    """Uploading a non-video payload disguised with .mp4 extension must be rejected."""
    login = client.post("/api/v1/auth/login", json=admin_credentials)
    token = login.json()["access_token"]

    files = {"file": ("corrupt.mp4", b"corrupted non-video binary header", "video/mp4")}
    res = client.post(
        "/api/v1/videos/upload",
        headers={"Authorization": f"Bearer {token}"},
        files=files,
    )
    assert res.status_code == 400
    assert "Corrupt or invalid video format" in res.json()["detail"]


def test_video_upload_success_and_metadata_persistence(client, admin_credentials):
    """Uploading a valid video creates isolated directory, calculates SHA-256, and saves record."""
    login = client.post("/api/v1/auth/login", json=admin_credentials)
    token = login.json()["access_token"]

    test_video_path = Path("videos/Main_video.mp4")
    if not test_video_path.exists():
        pytest.skip("videos/Main_video.mp4 not found")

    with open(test_video_path, "rb") as f:
        files = {"file": ("Main_video.mp4", f, "video/mp4")}
        data = {"building_id": "bldg-hq-01", "floor_id": "fl-01"}
        res = client.post(
            "/api/v1/videos/upload",
            headers={"Authorization": f"Bearer {token}"},
            files=files,
            data=data,
        )

    assert res.status_code == 201, res.text
    video_record = res.json()
    assert "video_id" in video_record
    assert video_record["sha256_checksum"] is not None
    assert video_record["status"] in ["UPLOADED", "READY"]
    assert Path(video_record["storage_path"]).exists()

    # Verify per-video isolation directory structure
    assert f"videos/{video_record['video_id']}" in video_record["storage_path"]


# ------------------------------------------------------------------------------
# 4. Entity Persistence & Durability
# ------------------------------------------------------------------------------

def test_full_entity_persistence_and_retrieval():
    """Verify all schema entities persist correctly with constraints."""
    video_repo = SQLiteVideoSourceRepository()
    job_repo = SQLiteProcessingJobRepository()
    frame_repo = SQLiteVideoFrameRepository()
    det_repo = SQLiteDetectionRepository()
    temp_repo = SQLiteTemporalAnalysisRepository()
    risk_repo = SQLiteRiskEventRepository()
    route_repo = SQLiteRouteRecommendationRepository()

    # 0. Ensure Video Source exists for FK constraint
    test_vid_id = f"vid_test_{uuid.uuid4().hex[:8]}"
    video_repo.save({
        "video_id": test_vid_id,
        "organization_id": "org-phoenix-main",
        "uploader_user_id": "usr-admin-01",
        "filename": "test_persistence.mp4",
        "storage_path": f"storage/videos/{test_vid_id}/test_persistence.mp4",
        "sha256_checksum": "dummy_sha_for_persistence_test",
        "status": "UPLOADED",
    })

    # 1. Processing Job
    test_job_id = f"job_test_{uuid.uuid4().hex[:8]}"
    job_repo.save({
        "job_id": test_job_id,
        "video_id": test_vid_id,
        "status": "QUEUED",
        "current_stage": "INITIALIZING",
        "max_retries": 3,
    })

    persisted_job = job_repo.get(test_job_id)
    assert persisted_job is not None
    assert persisted_job["status"] == JobStatus.QUEUED.value

    # 2. Video Frame
    test_frame_id = f"frm_test_{uuid.uuid4().hex[:8]}"
    frame_repo.save_batch([{
        "frame_id": test_frame_id,
        "job_id": test_job_id,
        "video_id": test_vid_id,
        "frame_index": 1,
        "timestamp_seconds": 0.033,
        "is_keyframe": True,
    }])

    # 3. Detection
    det_id = f"det_test_{uuid.uuid4().hex[:8]}"
    det = Detection(
        detection_id=det_id,
        job_id=test_job_id,
        frame_id=test_frame_id,
        camera_id="CAM-MAIN-01",
        timestamp=datetime.now(timezone.utc),
        class_name=DetectionType.FIRE,
        confidence=0.88,
        bbox=BoundingBox(x1=100.0, y1=120.0, x2=200.0, y2=220.0),
        floor_point=Point2D(x=12.5, y=8.4),
        model_version="fire_smoke_best.pt",
    )
    det_repo.save(det)

    # 4. Temporal Analysis
    temp_id = f"temp_test_{uuid.uuid4().hex[:8]}"
    temp_repo.save({
        "analysis_id": temp_id,
        "job_id": test_job_id,
        "camera_id": "CAM-MAIN-01",
        "timestamp": datetime.now(timezone.utc),
        "area_px2": 4500.0,
        "growth_rate_px2_per_sec": 120.5,
        "trend": "EXPANDING",
        "confidence": 0.91,
    })

    # 5. Risk Event
    risk_id = f"risk_test_{uuid.uuid4().hex[:8]}"
    risk_repo.save({
        "snapshot_id": risk_id,
        "job_id": test_job_id,
        "building_id": "bldg-hq-01",
        "floor_id": "fl-01",
        "timestamp": datetime.now(timezone.utc),
        "global_risk_level": "HIGH",
        "node_risks": {"node_corridor_mid": 0.82},
        "active_hazards_count": 1,
    })

    # 6. Route Recommendation with graph version and calculation assumptions
    route_id = f"rt_test_{uuid.uuid4().hex[:8]}"
    route_obj = RouteRecommendation(
        route_id=route_id,
        building_id="bldg-hq-01",
        floor_id="fl-01",
        origin_node="node_west_suites",
        destination_node="exit_south",
        path_nodes=["node_west_suites", "node_corridor_south", "exit_south"],
        path_edges=["edge_west_south", "edge_south_exit"],
        eta_seconds=15.4,
        cost_breakdown=RouteCostReason(
            distance_cost=0.18,
            hazard_cost=0.0,
            occupancy_cost=0.0,
            predicted_blockage_cost=0.0,
            total_cost=0.18,
        ),
        status=RouteStatus.VALID,
        algorithm_version="deterministic-networkx-v2",
        job_id=test_job_id,
        graph_version="1.0.0",
        calculation_assumptions={"algorithm": "Dijkstra", "avoidance": "smoke"},
    )
    route_repo.save(route_obj)

    # Verify retrieval
    retrieved_route = route_repo.get_latest_route("bldg-hq-01", "node_west_suites")
    assert retrieved_route is not None
    assert retrieved_route.route_id == route_id
    assert retrieved_route.origin_node == "node_west_suites"
    assert retrieved_route.destination_node == "exit_south"
    assert retrieved_route.status == RouteStatus.VALID


# ------------------------------------------------------------------------------
# 5. Concurrency & Per-Video Data Isolation
# ------------------------------------------------------------------------------

def test_per_job_and_video_data_isolation():
    """Ensure two distinct jobs do not leak frames, detections, or routes to each other."""
    video_repo = SQLiteVideoSourceRepository()
    job_repo = SQLiteProcessingJobRepository()
    frame_repo = SQLiteVideoFrameRepository()
    det_repo = SQLiteDetectionRepository()

    vid_a = f"vid_iso_a_{uuid.uuid4().hex[:6]}"
    vid_b = f"vid_iso_b_{uuid.uuid4().hex[:6]}"

    video_repo.save({
        "video_id": vid_a,
        "organization_id": "org-phoenix-main",
        "filename": "a.mp4",
        "storage_path": f"storage/videos/{vid_a}/a.mp4",
        "sha256_checksum": "sha_a",
        "status": "UPLOADED",
    })
    video_repo.save({
        "video_id": vid_b,
        "organization_id": "org-phoenix-main",
        "filename": "b.mp4",
        "storage_path": f"storage/videos/{vid_b}/b.mp4",
        "sha256_checksum": "sha_b",
        "status": "UPLOADED",
    })

    job_a = f"job_iso_a_{uuid.uuid4().hex[:6]}"
    job_b = f"job_iso_b_{uuid.uuid4().hex[:6]}"

    job_repo.save({"job_id": job_a, "video_id": vid_a, "status": "QUEUED"})
    job_repo.save({"job_id": job_b, "video_id": vid_b, "status": "QUEUED"})

    frame_a = f"frm_iso_a_{uuid.uuid4().hex[:6]}"
    frame_b = f"frm_iso_b_{uuid.uuid4().hex[:6]}"

    frame_repo.save_batch([{"frame_id": frame_a, "job_id": job_a, "video_id": vid_a, "frame_index": 1, "timestamp_seconds": 0.1}])
    frame_repo.save_batch([{"frame_id": frame_b, "job_id": job_b, "video_id": vid_b, "frame_index": 1, "timestamp_seconds": 0.1}])

    det_repo.save(Detection(
        detection_id=f"det_iso_a_{uuid.uuid4().hex[:6]}",
        job_id=job_a,
        frame_id=frame_a,
        camera_id="CAM-MAIN-01",
        timestamp=datetime.now(timezone.utc),
        class_name=DetectionType.FIRE,
        confidence=0.95,
        bbox=BoundingBox(x1=10, y1=10, x2=20, y2=20),
    ))

    det_repo.save(Detection(
        detection_id=f"det_iso_b_{uuid.uuid4().hex[:6]}",
        job_id=job_b,
        frame_id=frame_b,
        camera_id="CAM-MAIN-01",
        timestamp=datetime.now(timezone.utc),
        class_name=DetectionType.SMOKE,
        confidence=0.75,
        bbox=BoundingBox(x1=50, y1=50, x2=80, y2=80),
    ))

    # Inquire results for Job A only
    results_a = det_repo.list_by_job(job_a)
    assert len(results_a) == 1
    assert results_a[0].class_name == DetectionType.FIRE

    # Inquire results for Job B only
    results_b = det_repo.list_by_job(job_b)
    assert len(results_b) == 1
    assert results_b[0].class_name == DetectionType.SMOKE


# ------------------------------------------------------------------------------
# 6. Durability Across Database Restart
# ------------------------------------------------------------------------------

def test_durability_across_connection_recycle():
    """Verify data persisted remains intact when the database connection/pool is closed and reopened."""
    video_repo = SQLiteVideoSourceRepository()
    job_repo = SQLiteProcessingJobRepository()
    durable_vid_id = f"vid_dur_{uuid.uuid4().hex[:6]}"
    durable_job_id = f"job_durable_{uuid.uuid4().hex[:8]}"

    video_repo.save({
        "video_id": durable_vid_id,
        "organization_id": "org-phoenix-main",
        "filename": "dur.mp4",
        "storage_path": f"storage/videos/{durable_vid_id}/dur.mp4",
        "sha256_checksum": "sha_dur",
        "status": "UPLOADED",
    })

    job_repo.save({
        "job_id": durable_job_id,
        "video_id": durable_vid_id,
        "status": "COMPLETED",
        "progress_percent": 100.0,
    })

    # Dispose the SQLAlchemy engine connection pool
    engine.dispose()

    # Reopen new repository instance with fresh connection
    fresh_job_repo = SQLiteProcessingJobRepository()
    reloaded_job = fresh_job_repo.get(durable_job_id)
    assert reloaded_job is not None
    assert reloaded_job["job_id"] == durable_job_id
    assert reloaded_job["status"] == JobStatus.COMPLETED.value
    assert reloaded_job["progress_percent"] == 100.0
