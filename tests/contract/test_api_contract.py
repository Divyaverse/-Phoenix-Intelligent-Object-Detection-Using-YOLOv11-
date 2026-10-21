"""
Integration and API contract tests for Phase 3 FastAPI Endpoints.
"""

from fastapi.testclient import TestClient
import pytest
from app.main import app

client = TestClient(app)


def test_system_health():
    response = client.get("/api/v1/system/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "HEALTHY"
    assert "services" in data


def test_system_readiness():
    response = client.get("/api/v1/system/ready")
    assert response.status_code == 200
    data = response.json()
    assert data["ready"] is True
    assert data["ai_status"] == "OPERATIONAL"


def test_login_success():
    payload = {
        "email": "admin@phoenix.local",
        "password": "AdminPass123!",
    }
    response = client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["role"] == "SUPERADMIN"


def test_login_invalid_credentials():
    payload = {
        "email": "admin@phoenix.local",
        "password": "WrongPassword!",
    }
    response = client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 401


def test_protected_routes_unauthenticated():
    response = client.get("/api/v1/incidents/current")
    assert response.status_code == 401


def test_protected_routes_authenticated():
    # Login first
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "responder@phoenix.local", "password": "ResponderPass123!"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Test incident
    inc_resp = client.get("/api/v1/incidents/current", headers=headers)
    assert inc_resp.status_code == 200
    assert "incident_id" in inc_resp.json()
    assert bool(inc_resp.json()["incident_id"])

    # Test route
    route_resp = client.get("/api/v1/routes/current?origin=room_101", headers=headers)
    assert route_resp.status_code == 200
    assert route_resp.json()["status"] == "VALID"
    assert "cost_breakdown" in route_resp.json()



def test_rbac_camera_access_occupant_denied():
    # Login as occupant
    login_resp = client.post(
        "/api/v1/auth/login",
        json={"email": "occupant@phoenix.local", "password": "OccupantPass123!"},
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Occupant attempting camera management endpoint
    cam_resp = client.get("/api/v1/cameras", headers=headers)
    assert cam_resp.status_code == 403
