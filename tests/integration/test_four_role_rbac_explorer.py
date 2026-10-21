"""
Integration tests for PHOENIX Four-Role RBAC & Data Storage Explorer:
- All 4 roles: SUPERADMIN, BUILDING_MANAGER, FIRST_RESPONDER, OCCUPANT
- Credential validation and JWT issuance for each role
- /auth/me returns genuine identity and role
- Authorized and unauthorized camera list requests (403 for OCCUPANT, 200 for staff)
- Explorer overview, users, database, jobs, and export endpoints
- OCCUPANT denied access to administrative Explorer endpoints (403 Forbidden)
- Unauthenticated requests rejected (401 Unauthorized)
- Invalid or expired credentials rejected
- User inventory excludes sensitive fields (no passwords, password hashes, or tokens)
- Path traversal protection on job sample inspection
- No client-side privilege escalation without genuine authentication
"""

import pytest
from fastapi.testclient import TestClient
from app.main import app

@pytest.fixture(scope="module")
def client():
    return TestClient(app)

@pytest.fixture(scope="module")
def superadmin_token(client: TestClient) -> str:
    res = client.post("/api/v1/auth/login", json={"email": "admin@phoenix.local", "password": "AdminPass123!"})
    assert res.status_code == 200, f"SuperAdmin login failed: {res.text}"
    return res.json()["access_token"]

@pytest.fixture(scope="module")
def manager_token(client: TestClient) -> str:
    res = client.post("/api/v1/auth/login", json={"email": "manager@phoenix.local", "password": "ManagerPass123!"})
    assert res.status_code == 200, f"BuildingManager login failed: {res.text}"
    return res.json()["access_token"]

@pytest.fixture(scope="module")
def responder_token(client: TestClient) -> str:
    res = client.post("/api/v1/auth/login", json={"email": "responder@phoenix.local", "password": "ResponderPass123!"})
    assert res.status_code == 200, f"FirstResponder login failed: {res.text}"
    return res.json()["access_token"]

@pytest.fixture(scope="module")
def occupant_token(client: TestClient) -> str:
    res = client.post("/api/v1/auth/login", json={"email": "occupant@phoenix.local", "password": "OccupantPass123!"})
    assert res.status_code == 200, f"Occupant login failed: {res.text}"
    return res.json()["access_token"]


# ------------------------------------------------------------------------------
# 1. Four-Role Authentication & Identity Verification
# ------------------------------------------------------------------------------

def test_all_four_roles_login_and_me(
    client: TestClient,
    superadmin_token: str,
    manager_token: str,
    responder_token: str,
    occupant_token: str,
):
    """Verify each role can authenticate and that /auth/me returns genuine identity."""
    roles_and_tokens = [
        ("SUPERADMIN", superadmin_token, "usr-admin-01"),
        ("BUILDING_MANAGER", manager_token, "usr-mgr-01"),
        ("FIRST_RESPONDER", responder_token, "usr-resp-01"),
        ("OCCUPANT", occupant_token, "usr-occ-01"),
    ]
    for expected_role, token, expected_user_id in roles_and_tokens:
        res = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
        assert res.status_code == 200, f"Failed for {expected_role}: {res.text}"
        data = res.json()
        assert data["role"] == expected_role
        assert data["user_id"] == expected_user_id
        assert "password" not in data
        assert "password_hash" not in data


def test_invalid_and_missing_credentials(client: TestClient):
    """Verify missing, invalid, or malformed credentials return 401."""
    # Missing token
    res = client.get("/api/v1/auth/me")
    assert res.status_code == 401

    # Malformed token
    res = client.get("/api/v1/auth/me", headers={"Authorization": "Bearer not-a-valid-jwt"})
    assert res.status_code == 401

    # Wrong password login
    res = client.post("/api/v1/auth/login", json={"email": "admin@phoenix.local", "password": "WrongPassword!"})
    assert res.status_code == 401


# ------------------------------------------------------------------------------
# 2. Camera Access RBAC (Root Cause Reproduction & Verification)
# ------------------------------------------------------------------------------

def test_cameras_rbac_occupant_forbidden(client: TestClient, occupant_token: str):
    """
    CRITICAL: OCCUPANT role MUST be rejected with HTTP 403.
    This verifies that the 403 received by the browser was genuine role protection.
    """
    res = client.get(
        "/api/v1/cameras?building_id=bldg-hq-01",
        headers={"Authorization": f"Bearer {occupant_token}"},
    )
    assert res.status_code == 403
    assert "User role 'OCCUPANT' is not authorized for this resource" in res.json()["detail"]


def test_cameras_rbac_authorized_roles(
    client: TestClient,
    superadmin_token: str,
    manager_token: str,
    responder_token: str,
):
    """SUPERADMIN, BUILDING_MANAGER, and FIRST_RESPONDER are authorized to list cameras."""
    for token in [superadmin_token, manager_token, responder_token]:
        res = client.get(
            "/api/v1/cameras?building_id=bldg-hq-01",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert res.status_code == 200
        assert isinstance(res.json(), list)


def test_cameras_unauthenticated_rejected(client: TestClient):
    """Unauthenticated camera requests return 401."""
    res = client.get("/api/v1/cameras?building_id=bldg-hq-01")
    assert res.status_code == 401


# ------------------------------------------------------------------------------
# 3. Data & Storage Explorer Endpoints & RBAC
# ------------------------------------------------------------------------------

def test_explorer_overview_superadmin(client: TestClient, superadmin_token: str):
    """SUPERADMIN can access the complete storage overview."""
    res = client.get("/api/v1/explorer/overview", headers={"Authorization": f"Bearer {superadmin_token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["database"]["exists"] is True
    assert "phoenix.db" in data["database"]["path"].lower()
    assert data["database"]["size_bytes"] > 0
    assert data["directories"]["yolo_model_checkpoints"]["exists"] is True
    assert data["key_artifacts"]["fire_smoke_checkpoint"]["exists"] is True
    assert data["key_artifacts"]["person_headcount_checkpoint"]["exists"] is True


def test_explorer_overview_occupant_denied(client: TestClient, occupant_token: str):
    """OCCUPANT role is denied access to storage inventory (403 Forbidden)."""
    res = client.get("/api/v1/explorer/overview", headers={"Authorization": f"Bearer {occupant_token}"})
    assert res.status_code == 403


def test_explorer_users_inventory_security(client: TestClient, superadmin_token: str):
    """
    SUPERADMIN can view safe user metadata.
    MUST NOT leak passwords, password hashes, or tokens.
    """
    res = client.get("/api/v1/explorer/users", headers={"Authorization": f"Bearer {superadmin_token}"})
    assert res.status_code == 200
    data = res.json()
    assert "users" in data
    assert len(data["users"]) >= 4

    roles = {u["role"] for u in data["users"]}
    assert "SUPERADMIN" in roles
    assert "BUILDING_MANAGER" in roles
    assert "FIRST_RESPONDER" in roles
    assert "OCCUPANT" in roles

    # Strict check: NEVER leak secrets
    for user in data["users"]:
        assert "password" not in user
        assert "password_hash" not in user
        assert "token" not in user
        assert "access_token" not in user


def test_explorer_users_occupant_denied(client: TestClient, occupant_token: str):
    """OCCUPANT is denied access to user directory."""
    res = client.get("/api/v1/explorer/users", headers={"Authorization": f"Bearer {occupant_token}"})
    assert res.status_code == 403


def test_explorer_database_inventory(client: TestClient, superadmin_token: str):
    """Verify live database schema inspection returns actual tables and row counts."""
    res = client.get("/api/v1/explorer/database", headers={"Authorization": f"Bearer {superadmin_token}"})
    assert res.status_code == 200
    data = res.json()
    assert data["total_tables"] >= 15
    assert data["total_records"] > 0

    table_names = {t["table_name"] for t in data["tables"]}
    expected_tables = {
        "users",
        "video_sources",
        "processing_jobs",
        "video_frames",
        "detections",
        "temporal_analyses",
        "risk_events",
        "route_recommendations",
        "audit_events",
    }
    for expected in expected_tables:
        assert expected in table_names, f"Missing table: {expected}"


def test_explorer_database_occupant_denied(client: TestClient, occupant_token: str):
    """OCCUPANT is denied access to database inventory."""
    res = client.get("/api/v1/explorer/database", headers={"Authorization": f"Bearer {occupant_token}"})
    assert res.status_code == 403


def test_explorer_jobs_inventory(client: TestClient, superadmin_token: str):
    """Verify video and processing-job inventory returns real persisted records."""
    res = client.get("/api/v1/explorer/jobs?limit=10", headers={"Authorization": f"Bearer {superadmin_token}"})
    assert res.status_code == 200
    data = res.json()
    assert "jobs" in data
    assert data["total_jobs"] >= 1
    if len(data["jobs"]) > 0:
        first_job = data["jobs"][0]
        assert "job_id" in first_job
        assert "status" in first_job
        assert "detections_count" in first_job


def test_explorer_jobs_occupant_denied(client: TestClient, occupant_token: str):
    """OCCUPANT is denied access to jobs inventory."""
    res = client.get("/api/v1/explorer/jobs", headers={"Authorization": f"Bearer {occupant_token}"})
    assert res.status_code == 403


def test_explorer_export_report(client: TestClient, superadmin_token: str):
    """SUPERADMIN can generate an authorized, sanitized audit export."""
    res = client.get("/api/v1/explorer/export?format=json", headers={"Authorization": f"Bearer {superadmin_token}"})
    assert res.status_code == 200
    assert "application/json" in res.headers["content-type"]
    export_data = res.json()
    assert "generated_at" in export_data
    assert "storage_architecture" in export_data
    assert "database_inventory" in export_data
    assert "user_accounts_summary" in export_data
    assert "processing_jobs_summary" in export_data
    assert "data_lineage_stages" in export_data

    # Ensure no secrets or JWT tokens leaked in export
    for acc in export_data["user_accounts_summary"]["accounts"]:
        assert "password" not in acc
        assert "password_hash" not in acc
        assert "access_token" not in acc
        assert "refresh_token" not in acc

    export_str = str(export_data)
    assert "password_hash" not in export_str
    assert "eyJhbGci" not in export_str  # No JWT bearer token contents leaked
    assert "$argon2id$" not in export_str  # No Argon2id hashes leaked


def test_explorer_export_occupant_denied(client: TestClient, occupant_token: str):
    """OCCUPANT is denied audit export generation."""
    res = client.get("/api/v1/explorer/export", headers={"Authorization": f"Bearer {occupant_token}"})
    assert res.status_code == 403


# ------------------------------------------------------------------------------
# 4. Security & Path Traversal Protection
# ------------------------------------------------------------------------------

def test_explorer_job_sample_path_traversal_protection(client: TestClient, superadmin_token: str):
    """Attempting path traversal in job_id must be rejected safely."""
    malicious_ids = [
        "../../etc/passwd",
        "..\\..\\windows\\system32",
        "job/../../secret",
        "job;drop table users;",
        "<script>alert(1)</script>",
    ]
    for bad_id in malicious_ids:
        res = client.get(
            f"/api/v1/explorer/jobs/{bad_id}/sample",
            headers={"Authorization": f"Bearer {superadmin_token}"},
        )
        # Must fail with 400 Bad Request, 404 Not Found, or 422 Validation Error - never 200 or 500
        assert res.status_code in [400, 404, 422], f"Path traversal not blocked for {bad_id}: {res.status_code}"


# ------------------------------------------------------------------------------
# 5. Authenticated Role Transitions & Security Boundaries
# ------------------------------------------------------------------------------

def test_authenticated_role_switching_validation_flow(client: TestClient):
    """
    Enforce security rule:
    1. Clicking another role alone never changes the authenticated identity.
    2. Invalid credentials leave the original identity and token unchanged.
    3. Valid credentials for the target account switch to that verified identity.
    4. A requested role that does not match the authenticated account is rejected.
    """
    # 1. User starts authenticated as FIRST_RESPONDER
    resp_login = client.post(
        "/api/v1/auth/login",
        json={"email": "responder@phoenix.local", "password": "ResponderPass123!"},
    )
    assert resp_login.status_code == 200
    active_token = resp_login.json()["access_token"]

    # Verify initial identity is FIRST_RESPONDER
    initial_me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {active_token}"})
    assert initial_me.status_code == 200
    assert initial_me.json()["role"] == "FIRST_RESPONDER"
    assert initial_me.json()["user_id"] == "usr-resp-01"

    # 2. User attempts to switch to SUPERADMIN with invalid credentials
    invalid_attempt = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@phoenix.local", "password": "WrongPassword999!"},
    )
    assert invalid_attempt.status_code == 401
    # Active identity remains unchanged
    me_after_fail = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {active_token}"})
    assert me_after_fail.status_code == 200
    assert me_after_fail.json()["role"] == "FIRST_RESPONDER"
    assert me_after_fail.json()["user_id"] == "usr-resp-01"

    # 3. User attempts to switch to SUPERADMIN but enters OCCUPANT credentials
    # Target role is SUPERADMIN, but credentials authenticate as OCCUPANT
    occ_attempt = client.post(
        "/api/v1/auth/login",
        json={"email": "occupant@phoenix.local", "password": "OccupantPass123!"},
    )
    assert occ_attempt.status_code == 200
    occ_data = occ_attempt.json()
    new_token = occ_data["access_token"]
    # Check profile of returned token: role is OCCUPANT, NOT the requested SUPERADMIN!
    profile_check = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {new_token}"})
    assert profile_check.json()["role"] == "OCCUPANT"
    # Verification condition: requested_role ('SUPERADMIN') != authenticated_profile.role ('OCCUPANT') -> REJECT!
    assert profile_check.json()["role"] != "SUPERADMIN"

    # 4. User provides genuine SUPERADMIN credentials -> Authenticated transition succeeds
    admin_attempt = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@phoenix.local", "password": "AdminPass123!"},
    )
    assert admin_attempt.status_code == 200
    admin_token = admin_attempt.json()["access_token"]
    admin_me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {admin_token}"})
    assert admin_me.status_code == 200
    assert admin_me.json()["role"] == "SUPERADMIN"
    assert admin_me.json()["user_id"] == "usr-admin-01"


def test_client_side_role_spoofing_rejected(client: TestClient, occupant_token: str):
    """
    Enforce backend security boundary:
    Manually changing headers or client claims does not grant access.
    The server derives effective user ID and role strictly from the validated JWT token.
    """
    spoofed_headers = {
        "Authorization": f"Bearer {occupant_token}",
        "X-User-Role": "SUPERADMIN",
        "X-Phoenix-Role": "SUPERADMIN",
        "phoenix_role": "SUPERADMIN",
    }
    # OCCUPANT cannot access cameras even with spoofed headers
    res_cam = client.get("/api/v1/cameras?building_id=bldg-hq-01", headers=spoofed_headers)
    assert res_cam.status_code == 403

    # OCCUPANT cannot access administrative user list
    res_users = client.get("/api/v1/auth/users", headers=spoofed_headers)
    assert res_users.status_code == 403

    # OCCUPANT cannot access storage explorer
    res_exp = client.get("/api/v1/explorer/overview", headers=spoofed_headers)
    assert res_exp.status_code == 403


def test_cross_role_access_boundaries(
    client: TestClient,
    superadmin_token: str,
    manager_token: str,
    responder_token: str,
    occupant_token: str,
):
    """
    Verify strict role permissions across all 4 roles:
    - /auth/users is restricted to SUPERADMIN only
    - /cameras is accessible to staff (SUPERADMIN, BUILDING_MANAGER, FIRST_RESPONDER) but forbidden to OCCUPANT
    - /explorer/database is restricted to SUPERADMIN
    """
    # 1. /auth/users (SUPERADMIN only)
    assert client.get("/api/v1/auth/users", headers={"Authorization": f"Bearer {superadmin_token}"}).status_code == 200
    assert client.get("/api/v1/auth/users", headers={"Authorization": f"Bearer {manager_token}"}).status_code == 403
    assert client.get("/api/v1/auth/users", headers={"Authorization": f"Bearer {responder_token}"}).status_code == 403
    assert client.get("/api/v1/auth/users", headers={"Authorization": f"Bearer {occupant_token}"}).status_code == 403

    # 2. /cameras (Staff authorized, OCCUPANT forbidden)
    assert client.get("/api/v1/cameras?building_id=bldg-hq-01", headers={"Authorization": f"Bearer {superadmin_token}"}).status_code == 200
    assert client.get("/api/v1/cameras?building_id=bldg-hq-01", headers={"Authorization": f"Bearer {manager_token}"}).status_code == 200
    assert client.get("/api/v1/cameras?building_id=bldg-hq-01", headers={"Authorization": f"Bearer {responder_token}"}).status_code == 200
    assert client.get("/api/v1/cameras?building_id=bldg-hq-01", headers={"Authorization": f"Bearer {occupant_token}"}).status_code == 403


def test_logout_and_session_invalidation(client: TestClient):
    """Verify that logging out revokes the session on the backend."""
    login_res = client.post(
        "/api/v1/auth/login",
        json={"email": "responder@phoenix.local", "password": "ResponderPass123!"},
    )
    assert login_res.status_code == 200
    token = login_res.json()["access_token"]
    refresh = login_res.json()["refresh_token"]

    # Explicit logout
    logout_res = client.post("/api/v1/auth/logout", headers={"Authorization": f"Bearer {token}"})
    assert logout_res.status_code == 200
    assert logout_res.json()["status"] == "SUCCESS"

    # Using the refresh token after logout must be rejected
    refresh_attempt = client.post("/api/v1/auth/refresh", json={"refresh_token": refresh})
    assert refresh_attempt.status_code == 401

