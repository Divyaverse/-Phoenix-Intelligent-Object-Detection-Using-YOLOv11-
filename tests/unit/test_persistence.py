"""
Unit and integration tests for SQLite persistence, transactions, and repositories.
"""

import os
import pytest
from app.core.config import settings
from app.db.sqlite import db_transaction, init_db
from app.db.repositories import SQLiteAuditEventRepository, SQLiteUserRepository
from app.domain.models import AuditEvent, User
from app.domain.enums import UserRole
from app.core.errors import PersistenceUnavailableError


@pytest.fixture(autouse=True)
def setup_test_db(tmp_path):
    db_file = tmp_path / "test_phoenix.db"
    old_url = settings.database_url
    settings.database_url = f"sqlite:///{db_file}"
    init_db()
    yield
    settings.database_url = old_url


def test_user_repository_save_and_find():
    repo = SQLiteUserRepository()
    with db_transaction() as conn:
        conn.execute("INSERT INTO organizations (organization_id, name, created_at) VALUES ('org-test', 'Test Org', '2026-01-01');")

    user = User(
        user_id="usr-test-01",
        organization_id="org-test",
        email="test@phoenix.local",
        hashed_password="hashed_secret_123",
        full_name="Test Operator",
        role=UserRole.BUILDING_MANAGER,
    )
    repo.save(user)

    fetched = repo.find_by_email("test@phoenix.local")
    assert fetched is not None
    assert fetched.user_id == "usr-test-01"
    assert fetched.role == UserRole.BUILDING_MANAGER


def test_audit_repository_idempotency():
    repo = SQLiteAuditEventRepository()
    with db_transaction() as conn:
        conn.execute("INSERT INTO organizations (organization_id, name, created_at) VALUES ('org-test', 'Test Org', '2026-01-01');")

    event = AuditEvent(
        audit_id="aud-001",
        organization_id="org-test",
        action="ROUTE_RECOMPUTED",
        entity_type="RouteRecommendation",
        entity_id="route-101",
        reason="Smoke detected in corridor",
    )

    # First insertion succeeded
    first_try = repo.record_event(event, idempotency_key="idemp-key-999")
    assert first_try is True

    # Duplicate insertion skipped idempotently
    second_try = repo.record_event(event, idempotency_key="idemp-key-999")
    assert second_try is False


def test_transaction_rollback_on_error():
    with pytest.raises(PersistenceUnavailableError):
        with db_transaction() as conn:
            conn.execute("INSERT INTO organizations (organization_id, name, created_at) VALUES ('org-1', 'Org 1', 'now');")
            # Intentionally cause a SQL error
            conn.execute("INSERT INTO invalid_table_does_not_exist VALUES (1);")

def test_camera_incident_route_repositories():
    with db_transaction() as conn:
        conn.execute("INSERT INTO organizations (organization_id, name, created_at) VALUES ('org-test', 'Test Org', '2026-01-01');")
        conn.execute("INSERT INTO buildings (building_id, organization_id, name, address) VALUES ('bldg-1', 'org-test', 'HQ', 'Addr');")
        conn.execute("INSERT INTO floors (floor_id, building_id, floor_number, name, width_meters, height_meters) VALUES ('fl-1', 'bldg-1', 1, 'Floor 1', 50, 50);")

    from app.db.repositories import SQLiteCameraRepository, SQLiteIncidentRepository, SQLiteRouteRecommendationRepository
    from app.domain.models import Camera, Incident, RouteRecommendation, RouteCostReason
    from app.domain.enums import CameraStatus, IncidentSeverity, IncidentStatus, RouteStatus
    from datetime import datetime, timezone

    # 1. Camera Repo Test
    cam_repo = SQLiteCameraRepository()
    cam = Camera(
        camera_id="cam-101",
        organization_id="org-test",
        building_id="bldg-1",
        floor_id="fl-1",
        name="North Cam",
        source_uri="videos/test1.mp4",
        status=CameraStatus.ONLINE,
        monitored_nodes=["node1", "node2"],
    )
    cam_repo.save(cam)
    fetched_cam = cam_repo.get("cam-101")
    assert fetched_cam is not None
    assert fetched_cam.status == CameraStatus.ONLINE

    # 2. Incident Repo Test
    inc_repo = SQLiteIncidentRepository()
    inc = Incident(
        incident_id="inc-101",
        organization_id="org-test",
        building_id="bldg-1",
        floor_id="fl-1",
        status=IncidentStatus.CONFIRMED,
        severity=IncidentSeverity.HIGH,
        title="Fire Detected",
        affected_nodes=["node1"],
    )
    inc_repo.save(inc)
    fetched_inc = inc_repo.get_current_by_building("bldg-1")
    assert fetched_inc is not None
    assert fetched_inc.severity == IncidentSeverity.HIGH

    # 3. Route Repo Test
    route_repo = SQLiteRouteRecommendationRepository()
    route = RouteRecommendation(
        route_id="route-101",
        building_id="bldg-1",
        floor_id="fl-1",
        origin_node="node1",
        destination_node="exit_north",
        path_nodes=["node1", "exit_north"],
        path_edges=["e1"],
        status=RouteStatus.VALID,
        eta_seconds=12.5,
        total_cost=0.45,
        cost_breakdown=RouteCostReason(distance_cost=0.3, hazard_cost=0.15, occupancy_cost=0.0, predicted_blockage_cost=0.0, total_cost=0.45),
    )
    # 4. Floorplan Repo Test
    from app.db.repositories import SQLiteFloorplanRepository
    from app.spatial.floorplan_parser import FloorplanProcessor
    fp_repo = SQLiteFloorplanRepository()
    processor = FloorplanProcessor()
    fp = processor.create_synthetic_architectural_floorplan("bldg-1", "fl-1", "Persisted Floor")
    fp_repo.save(fp)
    fetched_fp = fp_repo.get_by_floor("bldg-1", "fl-1")
    assert fetched_fp is not None
    assert fetched_fp.name == "Persisted Floor"
    assert len(fetched_fp.nodes) == len(fp.nodes)

    # 5. Detection Repo Test
    from app.db.repositories import SQLiteDetectionRepository
    from app.domain.models import BoundingBox, Detection, Point2D
    from app.domain.enums import DetectionType
    det_repo = SQLiteDetectionRepository()
    det = Detection(
        detection_id="det-test-01",
        frame_id="f_00001",
        camera_id="cam-101",
        class_name=DetectionType.FIRE,
        confidence=0.88,
        bbox=BoundingBox(x1=10.0, y1=10.0, x2=50.0, y2=50.0),
        floor_point=Point2D(x=12.0, y=14.0),
    )
    det_repo.save(det)
    recent = det_repo.list_recent(camera_id="cam-101", limit=10)
    assert len(recent) == 1
    assert recent[0].class_name == DetectionType.FIRE
    assert recent[0].confidence == 0.88
    assert recent[0].floor_point is not None
    assert recent[0].floor_point.x == 12.0


