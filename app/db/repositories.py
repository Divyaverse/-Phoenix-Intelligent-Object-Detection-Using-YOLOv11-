"""
Repository implementations using SQLite for PHOENIX domain models.
Enforces atomic transactions, idempotency keys, and explicit failure reporting.
"""

import json
from datetime import datetime, timezone
from typing import Any, Optional
from app.db.sqlite import db_transaction
from app.domain.models import (
    AuditEvent,
    BoundingBox,
    Building,
    Camera,
    Detection,
    Floor,
    Incident,
    Organization,
    Point2D,
    RouteRecommendation,
    User,
)
from app.domain.enums import (
    CameraStatus,
    DetectionType,
    IncidentSeverity,
    IncidentStatus,
    RouteStatus,
    UserRole,
)
from app.core.errors import PersistenceUnavailableError


class SQLiteUserRepository:
    """Repository for managing Users in SQLite."""

    def save(self, user: User) -> None:
        sql = """
        INSERT INTO users (user_id, organization_id, email, hashed_password, full_name, role, is_active, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(user_id) DO UPDATE SET
            email=excluded.email,
            hashed_password=excluded.hashed_password,
            full_name=excluded.full_name,
            role=excluded.role,
            is_active=excluded.is_active;
        """
        with db_transaction() as conn:
            conn.execute(
                sql,
                (
                    user.user_id,
                    user.organization_id,
                    user.email.lower(),
                    user.hashed_password,
                    user.full_name,
                    user.role.value if isinstance(user.role, UserRole) else str(user.role),
                    1 if user.is_active else 0,
                    user.created_at.isoformat(),
                ),
            )

    def find_by_email(self, email: str) -> Optional[User]:
        sql = "SELECT * FROM users WHERE LOWER(email) = ?;"
        with db_transaction() as conn:
            cur = conn.execute(sql, (email.lower(),))
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_user(row)

    def find_by_id(self, user_id: str) -> Optional[User]:
        sql = "SELECT * FROM users WHERE user_id = ?;"
        with db_transaction() as conn:
            cur = conn.execute(sql, (user_id,))
            row = cur.fetchone()
            if not row:
                return None
            return self._row_to_user(row)

    def list_all(self, organization_id: Optional[str] = None) -> list[User]:
        sql = "SELECT * FROM users"
        params = ()
        if organization_id:
            sql += " WHERE organization_id = ?"
            params = (organization_id,)
        sql += " ORDER BY created_at ASC;"
        with db_transaction() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_user(r) for r in rows]

    def count(self) -> int:
        sql = "SELECT COUNT(*) FROM users;"
        with db_transaction() as conn:
            return conn.execute(sql).fetchone()[0]

    def update_status(self, user_id: str, is_active: bool) -> bool:
        sql = "UPDATE users SET is_active = ?, updated_at = ? WHERE user_id = ?;"
        with db_transaction() as conn:
            cur = conn.execute(sql, (1 if is_active else 0, datetime.now(timezone.utc).isoformat(), user_id))
            return cur.rowcount > 0

    def delete(self, user_id: str) -> bool:
        sql = "DELETE FROM users WHERE user_id = ?;"
        with db_transaction() as conn:
            cur = conn.execute(sql, (user_id,))
            return cur.rowcount > 0

    def _row_to_user(self, row) -> User:
        return User(
            user_id=row["user_id"],
            organization_id=row["organization_id"],
            email=row["email"],
            hashed_password=row["hashed_password"],
            full_name=row["full_name"],
            role=UserRole(row["role"]),
            is_active=bool(row["is_active"]),
            created_at=datetime.fromisoformat(row["created_at"]),
        )


class SQLiteAuditEventRepository:
    """Repository for persisting auditable events with idempotency guarantees."""

    def record_event(self, event: AuditEvent, idempotency_key: Optional[str] = None) -> bool:
        """
        Record audit event atomically. Returns True if inserted, False if idempotent duplicate key skipped.
        """
        sql = """
        INSERT INTO audit_events (
            audit_id, timestamp, organization_id, user_id, action,
            entity_type, entity_id, before_state_json, after_state_json,
            reason, metadata_json, idempotency_key
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(idempotency_key) DO NOTHING;
        """
        key = idempotency_key or event.audit_id
        with db_transaction() as conn:
            cur = conn.execute(
                sql,
                (
                    event.audit_id,
                    event.timestamp.isoformat(),
                    event.organization_id,
                    event.user_id,
                    event.action,
                    event.entity_type,
                    event.entity_id,
                    json.dumps(event.before_state) if event.before_state else None,
                    json.dumps(event.after_state) if event.after_state else None,
                    event.reason,
                    json.dumps(event.metadata),
                    key,
                ),
            )
            return cur.rowcount > 0

    def list_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        sql = "SELECT * FROM audit_events ORDER BY timestamp DESC LIMIT ?;"
        with db_transaction() as conn:
            rows = conn.execute(sql, (limit,)).fetchall()
            return [dict(r) for r in rows]


class SQLiteOrganizationRepository:
    """Repository for managing Organizations in SQLite."""

    def save(self, organization) -> None:
        sql = """
        INSERT INTO organizations (
            organization_id, name, created_at
        )
        VALUES (?, ?, ?)
        ON CONFLICT(organization_id) DO UPDATE SET
            name=excluded.name;
        """

        with db_transaction() as conn:
            conn.execute(
                sql,
                (
                    organization.organization_id,
                    organization.name,
                    organization.created_at.isoformat(),
                ),
            )

    def get(self, organization_id: str):
        sql = """
        SELECT * FROM organizations
        WHERE organization_id = ?;
        """

        with db_transaction() as conn:
            row = conn.execute(sql, (organization_id,)).fetchone()

            if not row:
                return None

            from app.domain.models import Organization

            return Organization(
                organization_id=row["organization_id"],
                name=row["name"],
                created_at=datetime.fromisoformat(row["created_at"]),
            )


class SQLiteBuildingRepository:
    """Repository for managing Buildings in SQLite."""

    def save(self, building: Building) -> None:
        sql = """
        INSERT INTO buildings (
            building_id,
            organization_id,
            name,
            address
        )
        VALUES (?, ?, ?, ?)
        ON CONFLICT(building_id) DO UPDATE SET
            organization_id=excluded.organization_id,
            name=excluded.name,
            address=excluded.address;
        """

        with db_transaction() as conn:
            conn.execute(
                sql,
                (
                    building.building_id,
                    building.organization_id,
                    building.name,
                    building.address,
                ),
            )

    def get(self, building_id: str) -> Optional[Building]:
        sql = """
        SELECT * FROM buildings
        WHERE building_id = ?;
        """

        with db_transaction() as conn:
            row = conn.execute(sql, (building_id,)).fetchone()

            if not row:
                return None

            return Building(
                building_id=row["building_id"],
                organization_id=row["organization_id"],
                name=row["name"],
                address=row["address"],
            )


class SQLiteFloorRepository:
    """Repository for managing Floors in SQLite."""

    def save(self, floor: Floor) -> None:
        sql = """
        INSERT INTO floors (
            floor_id,
            building_id,
            floor_number,
            name,
            width_meters,
            height_meters,
            floorplan_image_url
        )
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(floor_id) DO UPDATE SET
            building_id=excluded.building_id,
            floor_number=excluded.floor_number,
            name=excluded.name,
            width_meters=excluded.width_meters,
            height_meters=excluded.height_meters,
            floorplan_image_url=excluded.floorplan_image_url;
        """

        with db_transaction() as conn:
            conn.execute(
                sql,
                (
                    floor.floor_id,
                    floor.building_id,
                    floor.floor_number,
                    floor.name,
                    floor.width_meters,
                    floor.height_meters,
                    floor.floorplan_image_url,
                ),
            )

    def get(self, floor_id: str) -> Optional[Floor]:
        sql = """
        SELECT * FROM floors
        WHERE floor_id = ?;
        """

        with db_transaction() as conn:
            row = conn.execute(sql, (floor_id,)).fetchone()

            if not row:
                return None

            return Floor(
                floor_id=row["floor_id"],
                building_id=row["building_id"],
                floor_number=row["floor_number"],
                name=row["name"],
                width_meters=row["width_meters"],
                height_meters=row["height_meters"],
                floorplan_image_url=row["floorplan_image_url"],
            )


class SQLiteCameraRepository:
    """Repository for managing Cameras in SQLite."""

    def save(self, camera: Camera) -> None:
        sql = """
        INSERT INTO cameras (
            camera_id, organization_id, building_id, floor_id, name, source_uri, status, monitored_nodes_json, last_seen_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(camera_id) DO UPDATE SET
            status=excluded.status,
            monitored_nodes_json=excluded.monitored_nodes_json,
            last_seen_at=excluded.last_seen_at;
        """
        with db_transaction() as conn:
            conn.execute(
                sql,
                (
                    camera.camera_id,
                    camera.organization_id,
                    camera.building_id,
                    camera.floor_id,
                    camera.name,
                    camera.source_uri,
                    camera.status.value if isinstance(camera.status, CameraStatus) else str(camera.status),
                    json.dumps(camera.monitored_nodes),
                    camera.last_seen_at.isoformat() if camera.last_seen_at else None,
                ),
            )

    def get(self, camera_id: str) -> Optional[Camera]:
        sql = "SELECT * FROM cameras WHERE camera_id = ?;"
        with db_transaction() as conn:
            row = conn.execute(sql, (camera_id,)).fetchone()
            if not row:
                return None
            return Camera(
                camera_id=row["camera_id"],
                organization_id=row["organization_id"],
                building_id=row["building_id"],
                floor_id=row["floor_id"],
                name=row["name"],
                source_uri=row["source_uri"],
                status=CameraStatus(row["status"]),
                monitored_nodes=json.loads(row["monitored_nodes_json"]) if row["monitored_nodes_json"] else [],
                last_seen_at=datetime.fromisoformat(row["last_seen_at"]) if row["last_seen_at"] else None,
            )

    def list_by_building(self, building_id: str) -> list[Camera]:
        sql = "SELECT * FROM cameras WHERE building_id = ?;"
        with db_transaction() as conn:
            rows = conn.execute(sql, (building_id,)).fetchall()
            return [
                Camera(
                    camera_id=r["camera_id"],
                    organization_id=r["organization_id"],
                    building_id=r["building_id"],
                    floor_id=r["floor_id"],
                    name=r["name"],
                    source_uri=r["source_uri"],
                    status=CameraStatus(r["status"]),
                    monitored_nodes=json.loads(r["monitored_nodes_json"]) if r["monitored_nodes_json"] else [],
                    last_seen_at=datetime.fromisoformat(r["last_seen_at"]) if r["last_seen_at"] else None,
                )
                for r in rows
            ]


class SQLiteIncidentRepository:
    """Repository for managing Incidents in SQLite."""

    def save(self, incident: Incident) -> None:
        sql = """
        INSERT INTO incidents (
            incident_id, organization_id, building_id, floor_id, status, severity,
            title, description, hazard_origin_node, affected_nodes_json, declared_at, updated_at, resolved_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(incident_id) DO UPDATE SET
            status=excluded.status,
            severity=excluded.severity,
            title=excluded.title,
            description=excluded.description,
            hazard_origin_node=excluded.hazard_origin_node,
            affected_nodes_json=excluded.affected_nodes_json,
            updated_at=excluded.updated_at,
            resolved_at=excluded.resolved_at;
        """
        with db_transaction() as conn:
            conn.execute(
                sql,
                (
                    incident.incident_id,
                    incident.organization_id,
                    incident.building_id,
                    incident.floor_id,
                    incident.status.value if isinstance(incident.status, IncidentStatus) else str(incident.status),
                    incident.severity.value if isinstance(incident.severity, IncidentSeverity) else str(incident.severity),
                    incident.title,
                    incident.description,
                    incident.hazard_origin_node,
                    json.dumps(incident.affected_nodes),
                    incident.declared_at.isoformat(),
                    incident.updated_at.isoformat(),
                    incident.resolved_at.isoformat() if incident.resolved_at else None,
                ),
            )

    def get_current_by_building(self, building_id: str) -> Optional[Incident]:
        sql = "SELECT * FROM incidents WHERE building_id = ? AND status != 'CLOSED' ORDER BY declared_at DESC LIMIT 1;"
        with db_transaction() as conn:
            row = conn.execute(sql, (building_id,)).fetchone()
            if not row:
                return None
            return Incident(
                incident_id=row["incident_id"],
                organization_id=row["organization_id"],
                building_id=row["building_id"],
                floor_id=row["floor_id"],
                status=IncidentStatus(row["status"]),
                severity=IncidentSeverity(row["severity"]),
                title=row["title"],
                description=row["description"],
                hazard_origin_node=row["hazard_origin_node"],
                affected_nodes=json.loads(row["affected_nodes_json"]) if row["affected_nodes_json"] else [],
                declared_at=datetime.fromisoformat(row["declared_at"]),
                updated_at=datetime.fromisoformat(row["updated_at"]),
                resolved_at=datetime.fromisoformat(row["resolved_at"]) if row["resolved_at"] else None,
            )


class SQLiteRouteRecommendationRepository:
    """Repository for managing Evacuation Route Recommendations in SQLite."""

    def save(self, route: RouteRecommendation) -> None:
        sql = """
        INSERT INTO route_recommendations (
            route_id, job_id, building_id, floor_id, graph_version, origin_node, destination_node, path_nodes_json,
            path_edges_json, status, eta_seconds, total_cost, cost_breakdown_json,
            algorithm_version, calculation_assumptions_json, is_degraded, computed_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(route_id) DO UPDATE SET
            job_id=excluded.job_id,
            graph_version=excluded.graph_version,
            origin_node=excluded.origin_node,
            destination_node=excluded.destination_node,
            path_nodes_json=excluded.path_nodes_json,
            path_edges_json=excluded.path_edges_json,
            status=excluded.status,
            eta_seconds=excluded.eta_seconds,
            total_cost=excluded.total_cost,
            cost_breakdown_json=excluded.cost_breakdown_json,
            algorithm_version=excluded.algorithm_version,
            calculation_assumptions_json=excluded.calculation_assumptions_json,
            is_degraded=excluded.is_degraded,
            computed_at=excluded.computed_at;
        """
        with db_transaction() as conn:
            conn.execute(
                sql,
                (
                    route.route_id,
                    route.job_id,
                    route.building_id,
                    route.floor_id,
                    route.graph_version,
                    route.origin_node,
                    route.destination_node,
                    json.dumps(route.path_nodes),
                    json.dumps(route.path_edges),
                    route.status.value if isinstance(route.status, RouteStatus) else str(route.status),
                    route.eta_seconds,
                    route.total_cost,
                    json.dumps(route.cost_breakdown.model_dump()),
                    route.algorithm_version,
                    json.dumps(route.calculation_assumptions) if route.calculation_assumptions else None,
                    1 if route.is_degraded else 0,
                    route.computed_at.isoformat(),
                ),
            )

    def _row_to_route(self, row) -> RouteRecommendation:
        from app.domain.models import RouteCostReason
        cost_data = json.loads(row["cost_breakdown_json"])
        keys = row.keys()
        assumptions = json.loads(row["calculation_assumptions_json"]) if ("calculation_assumptions_json" in keys and row["calculation_assumptions_json"]) else {}
        graph_v = row["graph_version"] if "graph_version" in keys and row["graph_version"] else "1.0.0"
        job_id = row["job_id"] if "job_id" in keys else None

        return RouteRecommendation(
            route_id=row["route_id"],
            job_id=job_id,
            building_id=row["building_id"],
            floor_id=row["floor_id"],
            graph_version=graph_v,
            origin_node=row["origin_node"],
            destination_node=row["destination_node"],
            path_nodes=json.loads(row["path_nodes_json"]),
            path_edges=json.loads(row["path_edges_json"]),
            status=RouteStatus(row["status"]),
            eta_seconds=row["eta_seconds"],
            total_cost=row["total_cost"],
            cost_breakdown=RouteCostReason(**cost_data),
            algorithm_version=row["algorithm_version"],
            calculation_assumptions=assumptions,
            is_degraded=bool(row["is_degraded"]),
            computed_at=datetime.fromisoformat(row["computed_at"]),
        )

    def get_latest_route(self, building_id: str, origin_node: str) -> Optional[RouteRecommendation]:
        sql = "SELECT * FROM route_recommendations WHERE building_id = ? AND origin_node = ? ORDER BY computed_at DESC LIMIT 1;"
        with db_transaction() as conn:
            row = conn.execute(sql, (building_id, origin_node)).fetchone()
            if not row:
                return None
            return self._row_to_route(row)

    def get_latest_route_for_building(self, building_id: str) -> Optional[RouteRecommendation]:
        sql = "SELECT * FROM route_recommendations WHERE building_id = ? ORDER BY computed_at DESC LIMIT 1;"
        with db_transaction() as conn:
            row = conn.execute(sql, (building_id,)).fetchone()
            if not row:
                return None
            return self._row_to_route(row)

    def list_by_job(self, job_id: str) -> list[RouteRecommendation]:
        sql = "SELECT * FROM route_recommendations WHERE job_id = ? ORDER BY computed_at ASC;"
        with db_transaction() as conn:
            rows = conn.execute(sql, (job_id,)).fetchall()
            return [self._row_to_route(r) for r in rows]


class SQLiteFloorplanRepository:
    """Repository for managing dynamic FloorplanModels in SQLite."""

    def save(self, floorplan: FloorplanModel) -> None:
        sql = """
        INSERT INTO floorplans (
            floorplan_id, building_id, floor_id, name, image_url,
            image_width_px, image_height_px, scale_reference_json,
            physical_width_meters, physical_height_meters, is_scale_calibrated,
            graph_version, regions_json, walls_json, doors_json, exits_json, nodes_json, edges_json,
            created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(floorplan_id) DO UPDATE SET
            name=excluded.name,
            image_url=excluded.image_url,
            scale_reference_json=excluded.scale_reference_json,
            physical_width_meters=excluded.physical_width_meters,
            physical_height_meters=excluded.physical_height_meters,
            is_scale_calibrated=excluded.is_scale_calibrated,
            graph_version=excluded.graph_version,
            regions_json=excluded.regions_json,
            walls_json=excluded.walls_json,
            doors_json=excluded.doors_json,
            exits_json=excluded.exits_json,
            nodes_json=excluded.nodes_json,
            edges_json=excluded.edges_json,
            updated_at=excluded.updated_at;
        """
        with db_transaction() as conn:
            conn.execute(
                sql,
                (
                    floorplan.floorplan_id,
                    floorplan.building_id,
                    floorplan.floor_id,
                    floorplan.name,
                    floorplan.image_url,
                    floorplan.image_width_px,
                    floorplan.image_height_px,
                    json.dumps(floorplan.scale_reference.model_dump(mode="json")) if floorplan.scale_reference else None,
                    floorplan.physical_width_meters,
                    floorplan.physical_height_meters,
                    1 if floorplan.is_scale_calibrated else 0,
                    getattr(floorplan, "graph_version", "1.0.0"),
                    json.dumps([r.model_dump(mode="json") for r in floorplan.regions], default=str),
                    json.dumps([[p.model_dump(mode="json") for p in w] for w in floorplan.walls], default=str),
                    json.dumps([d.model_dump(mode="json") for d in floorplan.doors], default=str),
                    json.dumps([e.model_dump(mode="json") for e in floorplan.exits], default=str),
                    json.dumps([n.model_dump(mode="json") for n in floorplan.nodes], default=str),
                    json.dumps([e.model_dump(mode="json") for e in floorplan.edges], default=str),
                    floorplan.created_at.isoformat(),
                    floorplan.updated_at.isoformat(),
                ),
            )

    def get(self, floorplan_id: str) -> Optional[FloorplanModel]:
        sql = "SELECT * FROM floorplans WHERE floorplan_id = ?;"
        with db_transaction() as conn:
            row = conn.execute(sql, (floorplan_id,)).fetchone()
            if not row:
                return None
            return self._row_to_model(row)

    def get_by_floor(self, building_id: str, floor_id: str) -> Optional[FloorplanModel]:
        sql = "SELECT * FROM floorplans WHERE building_id = ? AND floor_id = ? ORDER BY updated_at DESC LIMIT 1;"
        with db_transaction() as conn:
            row = conn.execute(sql, (building_id, floor_id)).fetchone()
            if not row:
                return None
            return self._row_to_model(row)

    def _row_to_model(self, row) -> FloorplanModel:
        from app.domain.models import FloorplanModel, NavigationEdge, NavigationNode, Point2D, ScaleReference, SpatialRegion
        scale_ref = ScaleReference(**json.loads(row["scale_reference_json"])) if row["scale_reference_json"] else None
        regions = [SpatialRegion(**r) for r in json.loads(row["regions_json"])] if row["regions_json"] else []
        walls = [[Point2D(**p) for p in w] for w in json.loads(row["walls_json"])] if row["walls_json"] else []
        doors = [Point2D(**d) for d in json.loads(row["doors_json"])] if row["doors_json"] else []
        exits = [Point2D(**e) for e in json.loads(row["exits_json"])] if row["exits_json"] else []
        nodes = [NavigationNode(**n) for n in json.loads(row["nodes_json"])] if row["nodes_json"] else []
        edges = [NavigationEdge(**e) for e in json.loads(row["edges_json"])] if row["edges_json"] else []
        keys = row.keys()
        graph_v = row["graph_version"] if "graph_version" in keys and row["graph_version"] else "1.0.0"

        return FloorplanModel(
            floorplan_id=row["floorplan_id"],
            building_id=row["building_id"],
            floor_id=row["floor_id"],
            name=row["name"],
            image_url=row["image_url"],
            image_width_px=row["image_width_px"],
            image_height_px=row["image_height_px"],
            scale_reference=scale_ref,
            physical_width_meters=row["physical_width_meters"],
            physical_height_meters=row["physical_height_meters"],
            is_scale_calibrated=bool(row["is_scale_calibrated"]),
            graph_version=graph_v,
            regions=regions,
            walls=walls,
            doors=doors,
            exits=exits,
            nodes=nodes,
            edges=edges,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )


class SQLiteDetectionRepository:
    """Repository for managing perceived Detections in SQLite."""

    def save(self, detection: Detection) -> None:
        sql = """
        INSERT INTO detections (
            detection_id, job_id, frame_id, camera_id, timestamp, class_name, confidence, bbox_json, floor_point_json, model_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(detection_id) DO NOTHING;
        """
        det_id = detection.detection_id or f"det_{detection.camera_id}_{detection.frame_id}_{detection.class_name.value}_{datetime.now(timezone.utc).timestamp():.4f}"
        bbox_data = {
            "x1": detection.bbox.x1,
            "y1": detection.bbox.y1,
            "x2": detection.bbox.x2,
            "y2": detection.bbox.y2,
        }
        floor_point_data = (
            {"x": detection.floor_point.x, "y": detection.floor_point.y}
            if detection.floor_point
            else None
        )
        with db_transaction() as conn:
            conn.execute(
                sql,
                (
                    det_id,
                    detection.job_id,
                    detection.frame_id,
                    detection.camera_id,
                    detection.timestamp.isoformat(),
                    detection.class_name.value if isinstance(detection.class_name, DetectionType) else str(detection.class_name),
                    detection.confidence,
                    json.dumps(bbox_data),
                    json.dumps(floor_point_data) if floor_point_data else None,
                    getattr(detection, "model_version", "yolov11-dual"),
                ),
            )

    def save_batch(self, detections: list[Detection]) -> None:
        if not detections:
            return
        sql = """
        INSERT INTO detections (
            detection_id, job_id, frame_id, camera_id, timestamp, class_name, confidence, bbox_json, floor_point_json, model_version
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(detection_id) DO NOTHING;
        """
        rows = []
        for d in detections:
            det_id = d.detection_id or f"det_{d.camera_id}_{d.frame_id}_{d.class_name.value}_{d.timestamp.timestamp():.4f}"
            bbox_data = {"x1": d.bbox.x1, "y1": d.bbox.y1, "x2": d.bbox.x2, "y2": d.bbox.y2}
            floor_point_data = {"x": d.floor_point.x, "y": d.floor_point.y} if d.floor_point else None
            rows.append((
                det_id,
                d.job_id,
                d.frame_id,
                d.camera_id,
                d.timestamp.isoformat(),
                d.class_name.value if isinstance(d.class_name, DetectionType) else str(d.class_name),
                d.confidence,
                json.dumps(bbox_data),
                json.dumps(floor_point_data) if floor_point_data else None,
                getattr(d, "model_version", "yolov11-dual"),
            ))
        with db_transaction() as conn:
            conn.executemany(sql, rows)

    def list_recent(self, camera_id: Optional[str] = None, limit: int = 50) -> list[Detection]:
        if camera_id:
            sql = "SELECT * FROM detections WHERE camera_id = ? ORDER BY timestamp DESC LIMIT ?;"
            params = (camera_id, limit)
        else:
            sql = "SELECT * FROM detections ORDER BY timestamp DESC LIMIT ?;"
            params = (limit,)
        with db_transaction() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [self._row_to_detection(r) for r in rows]

    def list_by_job(self, job_id: str, limit: int = 1000) -> list[Detection]:
        sql = "SELECT * FROM detections WHERE job_id = ? ORDER BY timestamp ASC LIMIT ?;"
        with db_transaction() as conn:
            rows = conn.execute(sql, (job_id, limit)).fetchall()
            return [self._row_to_detection(r) for r in rows]

    def _row_to_detection(self, r) -> Detection:
        bbox_dict = json.loads(r["bbox_json"])
        bbox = BoundingBox(**bbox_dict)
        fp = Point2D(**json.loads(r["floor_point_json"])) if r["floor_point_json"] else None
        keys = r.keys()
        return Detection(
            detection_id=r["detection_id"],
            job_id=r["job_id"] if "job_id" in keys else None,
            frame_id=r["frame_id"],
            camera_id=r["camera_id"],
            timestamp=datetime.fromisoformat(r["timestamp"]),
            class_name=DetectionType(r["class_name"]),
            confidence=r["confidence"],
            bbox=bbox,
            floor_point=fp,
            model_version=r["model_version"] if "model_version" in keys and r["model_version"] else "yolov11-dual",
        )


class SQLiteAuthSessionRepository:
    """Repository for persisting revocable user authentication sessions."""

    def create_session(
        self,
        session_id: str,
        user_id: str,
        token_hash: str,
        expires_at: datetime,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        sql = """
        INSERT INTO auth_sessions (
            session_id, user_id, token_hash, ip_address, user_agent, device_info, is_revoked, expires_at, created_at, last_used_at
        ) VALUES (?, ?, ?, ?, ?, ?, 0, ?, ?, ?);
        """
        with db_transaction() as conn:
            conn.execute(
                sql,
                (
                    session_id,
                    user_id,
                    token_hash,
                    ip_address,
                    user_agent,
                    user_agent,
                    expires_at.isoformat(),
                    now,
                    now,
                ),
            )

    def find_by_token_hash(self, token_hash: str) -> Optional[dict[str, Any]]:
        sql = "SELECT * FROM auth_sessions WHERE token_hash = ? AND is_revoked = 0;"
        with db_transaction() as conn:
            row = conn.execute(sql, (token_hash,)).fetchone()
            return dict(row) if row else None

    def find_by_id(self, session_id: str) -> Optional[dict[str, Any]]:
        sql = "SELECT * FROM auth_sessions WHERE session_id = ?;"
        with db_transaction() as conn:
            row = conn.execute(sql, (session_id,)).fetchone()
            return dict(row) if row else None

    def revoke_session(self, session_id: str) -> bool:
        sql = "UPDATE auth_sessions SET is_revoked = 1, revoked_at = ? WHERE session_id = ?;"
        with db_transaction() as conn:
            cur = conn.execute(sql, (datetime.now(timezone.utc).isoformat(), session_id))
            return cur.rowcount > 0

    def revoke_by_token_hash(self, token_hash: str) -> bool:
        sql = "UPDATE auth_sessions SET is_revoked = 1, revoked_at = ? WHERE token_hash = ?;"
        with db_transaction() as conn:
            cur = conn.execute(sql, (datetime.now(timezone.utc).isoformat(), token_hash))
            return cur.rowcount > 0

    def revoke_all_user_sessions(self, user_id: str) -> int:
        sql = "UPDATE auth_sessions SET is_revoked = 1, revoked_at = ? WHERE user_id = ? AND is_revoked = 0;"
        with db_transaction() as conn:
            cur = conn.execute(sql, (datetime.now(timezone.utc).isoformat(), user_id))
            return cur.rowcount

    def delete_expired_sessions(self) -> int:
        now_iso = datetime.now(timezone.utc).isoformat()
        sql = "DELETE FROM auth_sessions WHERE expires_at < ?;"
        with db_transaction() as conn:
            cur = conn.execute(sql, (now_iso,))
            return cur.rowcount


class SQLiteCalibrationRepository:
    """Repository for camera spatial homography calibrations."""

    def save(self, calib: Calibration, condition_number: float = 1.0) -> None:
        sql = """
        INSERT INTO calibrations (
            calibration_id, camera_id, building_id, floor_id, matrix_3x3_json, points_json,
            reprojection_error, condition_number, is_valid, version, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(calibration_id) DO UPDATE SET
            matrix_3x3_json=excluded.matrix_3x3_json,
            points_json=excluded.points_json,
            reprojection_error=excluded.reprojection_error,
            condition_number=excluded.condition_number,
            is_valid=excluded.is_valid,
            version=excluded.version,
            updated_at=excluded.updated_at;
        """
        now = datetime.now(timezone.utc).isoformat()
        pts_json = json.dumps([p.model_dump(mode="json") for p in calib.points])
        with db_transaction() as conn:
            conn.execute(
                sql,
                (
                    calib.calibration_id,
                    calib.camera_id,
                    calib.building_id,
                    calib.floor_id,
                    json.dumps(calib.matrix_3x3),
                    pts_json,
                    calib.reprojection_error,
                    condition_number,
                    1 if calib.is_valid else 0,
                    calib.version,
                    calib.created_at.isoformat(),
                    now,
                ),
            )

    def get(self, calibration_id: str) -> Optional[Calibration]:
        sql = "SELECT * FROM calibrations WHERE calibration_id = ?;"
        with db_transaction() as conn:
            row = conn.execute(sql, (calibration_id,)).fetchone()
            return self._row_to_model(row) if row else None

    def get_by_camera(self, camera_id: str) -> Optional[Calibration]:
        sql = "SELECT * FROM calibrations WHERE camera_id = ? ORDER BY version DESC LIMIT 1;"
        with db_transaction() as conn:
            row = conn.execute(sql, (camera_id,)).fetchone()
            return self._row_to_model(row) if row else None

    def _row_to_model(self, row) -> Calibration:
        from app.domain.models import CalibrationPoint
        pts = [CalibrationPoint(**p) for p in json.loads(row["points_json"])] if row["points_json"] else []
        keys = row.keys()
        mat_str = row["matrix_3x3_json"] if "matrix_3x3_json" in keys else row.get("matrix_json", "[]")
        return Calibration(
            calibration_id=row["calibration_id"],
            camera_id=row["camera_id"],
            building_id=row["building_id"],
            floor_id=row["floor_id"],
            matrix_3x3=json.loads(mat_str) if mat_str else [],
            points=pts,
            version=row["version"],
            is_valid=bool(row["is_valid"]),
            reprojection_error=row["reprojection_error"],
            created_at=datetime.fromisoformat(row["created_at"]),
        )


class SQLiteVideoSourceRepository:
    """Repository for uploaded original video files and metadata."""

    def save(self, v: dict[str, Any]) -> None:
        sql = """
        INSERT INTO video_sources (
            video_id, organization_id, uploader_user_id, filename, original_name,
            storage_path, file_size_bytes, mime_type, sha256_checksum, status,
            fps, duration_seconds, resolution, original_filename, stored_filename,
            uploaded_by_user_id, width, height, error_message, created_at, updated_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(video_id) DO UPDATE SET
            status=excluded.status,
            error_message=excluded.error_message,
            duration_seconds=excluded.duration_seconds,
            fps=excluded.fps,
            width=excluded.width,
            height=excluded.height,
            updated_at=excluded.updated_at;
        """
        now = datetime.now(timezone.utc).isoformat()
        with db_transaction() as conn:
            conn.execute(
                sql,
                (
                    v["video_id"],
                    v.get("organization_id", "org-phoenix-main"),
                    v.get("uploaded_by_user_id") or v.get("uploader_user_id"),
                    v.get("stored_filename") or v.get("filename", "video.mp4"),
                    v.get("original_filename") or v.get("original_name", "video.mp4"),
                    v["storage_path"],
                    v.get("file_size_bytes", 0),
                    v.get("mime_type", "video/mp4"),
                    v["sha256_checksum"],
                    v.get("status", "UPLOADED"),
                    v.get("fps", 0.0),
                    v.get("duration_seconds", 0.0),
                    f"{v.get('width', 0)}x{v.get('height', 0)}",
                    v.get("original_filename") or v.get("original_name", "video.mp4"),
                    v.get("stored_filename") or v.get("filename", "video.mp4"),
                    v.get("uploaded_by_user_id") or v.get("uploader_user_id"),
                    v.get("width", 0),
                    v.get("height", 0),
                    v.get("error_message"),
                    v.get("created_at", now),
                    now,
                ),
            )

    def get(self, video_id: str) -> Optional[dict[str, Any]]:
        sql = "SELECT * FROM video_sources WHERE video_id = ?;"
        with db_transaction() as conn:
            row = conn.execute(sql, (video_id,)).fetchone()
            return dict(row) if row else None

    def list_all(self, organization_id: Optional[str] = None) -> list[dict[str, Any]]:
        sql = "SELECT * FROM video_sources"
        params = ()
        if organization_id:
            sql += " WHERE organization_id = ?"
            params = (organization_id,)
        sql += " ORDER BY created_at DESC;"
        with db_transaction() as conn:
            rows = conn.execute(sql, params).fetchall()
            return [dict(r) for r in rows]

    def update_status(self, video_id: str, status: str, error_message: Optional[str] = None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        sql = "UPDATE video_sources SET status = ?, error_message = ?, updated_at = ? WHERE video_id = ?;"
        with db_transaction() as conn:
            conn.execute(sql, (status, error_message, now, video_id))

    def delete(self, video_id: str) -> bool:
        sql = "DELETE FROM video_sources WHERE video_id = ?;"
        with db_transaction() as conn:
            cur = conn.execute(sql, (video_id,))
            return cur.rowcount > 0


class SQLiteProcessingJobRepository:
    """Repository for background video perception processing jobs."""

    def save(self, job: dict[str, Any]) -> None:
        sql = """
        INSERT INTO processing_jobs (
            job_id, video_id, camera_id, building_id, floor_id, status,
            progress_pct, current_frame, total_frames, retry_count, max_retries,
            error_message, error_details_json, annotated_video_path,
            started_at, completed_at, created_at, updated_at,
            current_stage, frames_processed, detections_count, fire_detected,
            smoke_detected, max_risk_level, progress_percent, execution_time_seconds,
            output_metadata_json, created_by_user_id, organization_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(job_id) DO UPDATE SET
            status=excluded.status,
            progress_pct=excluded.progress_pct,
            progress_percent=excluded.progress_percent,
            current_frame=excluded.current_frame,
            current_stage=excluded.current_stage,
            frames_processed=excluded.frames_processed,
            total_frames=excluded.total_frames,
            detections_count=excluded.detections_count,
            fire_detected=excluded.fire_detected,
            smoke_detected=excluded.smoke_detected,
            max_risk_level=excluded.max_risk_level,
            error_message=excluded.error_message,
            retry_count=excluded.retry_count,
            started_at=excluded.started_at,
            completed_at=excluded.completed_at,
            execution_time_seconds=excluded.execution_time_seconds,
            annotated_video_path=excluded.annotated_video_path,
            output_metadata_json=excluded.output_metadata_json,
            updated_at=excluded.updated_at;
        """
        now = datetime.now(timezone.utc).isoformat()
        meta = json.dumps(job.get("output_metadata")) if isinstance(job.get("output_metadata"), dict) else job.get("output_metadata_json")
        with db_transaction() as conn:
            conn.execute(
                sql,
                (
                    job["job_id"],
                    job["video_id"],
                    job.get("camera_id", "CAM-MAIN-01"),
                    job.get("building_id", "bldg-hq-01"),
                    job.get("floor_id", "fl-01"),
                    job.get("status", "QUEUED"),
                    job.get("progress_percent", 0.0),
                    job.get("frames_processed", 0),
                    job.get("total_frames", 0),
                    job.get("retry_count", 0),
                    job.get("max_retries", 3),
                    job.get("error_message"),
                    job.get("error_details_json"),
                    job.get("annotated_video_path"),
                    job.get("started_at"),
                    job.get("completed_at"),
                    job.get("created_at", now),
                    now,
                    job.get("current_stage", "INITIALIZING"),
                    job.get("frames_processed", 0),
                    job.get("detections_count", 0),
                    1 if job.get("fire_detected") else 0,
                    1 if job.get("smoke_detected") else 0,
                    job.get("max_risk_level", "LOW"),
                    job.get("progress_percent", 0.0),
                    job.get("execution_time_seconds"),
                    meta,
                    job.get("created_by_user_id"),
                    job.get("organization_id", "org-phoenix-main"),
                ),
            )

    def get(self, job_id: str) -> Optional[dict[str, Any]]:
        sql = "SELECT * FROM processing_jobs WHERE job_id = ?;"
        with db_transaction() as conn:
            row = conn.execute(sql, (job_id,)).fetchone()
            return dict(row) if row else None

    def update_progress(
        self,
        job_id: str,
        progress_percent: float,
        current_stage: str,
        frames_processed: int,
        detections_count: int,
        fire_detected: bool = False,
        smoke_detected: bool = False,
        max_risk: str = "LOW",
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        sql = """
        UPDATE processing_jobs SET
            progress_pct = ?,
            progress_percent = ?,
            current_frame = ?,
            frames_processed = ?,
            current_stage = ?,
            detections_count = ?,
            fire_detected = MAX(fire_detected, ?),
            smoke_detected = MAX(smoke_detected, ?),
            max_risk_level = ?,
            status = 'PROCESSING',
            updated_at = ?
        WHERE job_id = ?;
        """
        with db_transaction() as conn:
            conn.execute(
                sql,
                (
                    progress_percent,
                    progress_percent,
                    frames_processed,
                    frames_processed,
                    current_stage,
                    detections_count,
                    1 if fire_detected else 0,
                    1 if smoke_detected else 0,
                    max_risk,
                    now,
                    job_id,
                ),
            )

    def complete_job(
        self,
        job_id: str,
        annotated_video_path: Optional[str] = None,
        output_metadata: Optional[dict[str, Any]] = None,
        execution_time_seconds: Optional[float] = None,
    ) -> None:
        now = datetime.now(timezone.utc).isoformat()
        sql = """
        UPDATE processing_jobs SET
            status = 'COMPLETED',
            progress_pct = 100.0,
            progress_percent = 100.0,
            current_stage = 'FINISHED',
            completed_at = ?,
            annotated_video_path = COALESCE(?, annotated_video_path),
            output_metadata_json = COALESCE(?, output_metadata_json),
            execution_time_seconds = COALESCE(?, execution_time_seconds),
            updated_at = ?
        WHERE job_id = ?;
        """
        meta_json = json.dumps(output_metadata) if output_metadata else None
        with db_transaction() as conn:
            conn.execute(
                sql,
                (now, annotated_video_path, meta_json, execution_time_seconds, now, job_id),
            )

    def fail_job(self, job_id: str, error_message: str, error_code: Optional[str] = None) -> None:
        now = datetime.now(timezone.utc).isoformat()
        sql = """
        UPDATE processing_jobs SET
            status = 'FAILED',
            current_stage = 'FAILED',
            error_message = ?,
            error_details_json = ?,
            completed_at = ?,
            updated_at = ?
        WHERE job_id = ?;
        """
        with db_transaction() as conn:
            conn.execute(sql, (error_message, error_code or "PROCESSING_ERROR", now, now, job_id))

    def cancel_job(self, job_id: str) -> None:
        now = datetime.now(timezone.utc).isoformat()
        sql = """
        UPDATE processing_jobs SET
            status = 'CANCELLED',
            current_stage = 'CANCELLED',
            completed_at = ?,
            updated_at = ?
        WHERE job_id = ?;
        """
        with db_transaction() as conn:
            conn.execute(sql, (now, now, job_id))

    def list_by_video(self, video_id: str) -> list[dict[str, Any]]:
        sql = "SELECT * FROM processing_jobs WHERE video_id = ? ORDER BY created_at DESC;"
        with db_transaction() as conn:
            rows = conn.execute(sql, (video_id,)).fetchall()
            return [dict(r) for r in rows]

    def list_recent(self, limit: int = 50) -> list[dict[str, Any]]:
        sql = "SELECT * FROM processing_jobs ORDER BY created_at DESC LIMIT ?;"
        with db_transaction() as conn:
            rows = conn.execute(sql, (limit,)).fetchall()
            return [dict(r) for r in rows]


class SQLiteVideoFrameRepository:
    """Repository for video frame metadata and sample references."""

    def save_batch(self, frames: list[dict[str, Any]]) -> None:
        if not frames:
            return
        sql = """
        INSERT INTO video_frames (
            frame_id, job_id, video_id, frame_index, timestamp_seconds, frame_image_path,
            inference_latency_ms, detections_count, has_hazard, is_keyframe, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(frame_id) DO NOTHING;
        """
        now = datetime.now(timezone.utc).isoformat()
        rows = [
            (
                f["frame_id"],
                f["job_id"],
                f.get("video_id", "vid_default"),
                f["frame_index"],
                f["timestamp_seconds"],
                f.get("frame_image_path"),
                f.get("inference_latency_ms", 0.0),
                f.get("detections_count", 0),
                1 if f.get("has_hazard") else 0,
                1 if f.get("is_keyframe") else 0,
                f.get("created_at", now),
            )
            for f in frames
        ]
        with db_transaction() as conn:
            conn.executemany(sql, rows)

    def list_by_job(self, job_id: str, keyframes_only: bool = False) -> list[dict[str, Any]]:
        if keyframes_only:
            sql = "SELECT * FROM video_frames WHERE job_id = ? AND is_keyframe = 1 ORDER BY frame_index ASC;"
        else:
            sql = "SELECT * FROM video_frames WHERE job_id = ? ORDER BY frame_index ASC;"
        with db_transaction() as conn:
            rows = conn.execute(sql, (job_id,)).fetchall()
            return [dict(r) for r in rows]


class SQLiteTemporalAnalysisRepository:
    """Repository for temporal smoke growth rate tracking."""

    def save(self, rec: dict[str, Any]) -> None:
        self.save_batch([rec])

    def save_batch(self, records: list[dict[str, Any]]) -> None:
        if not records:
            return
        sql = """
        INSERT INTO temporal_analyses (
            analysis_id, job_id, camera_id, timestamp, area_px2, delta_area_px2,
            dt_seconds, growth_rate_px2_per_sec, smoothed_growth_rate, trend,
            confidence, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(analysis_id) DO NOTHING;
        """
        now = datetime.now(timezone.utc).isoformat()
        rows = [
            (
                r["analysis_id"],
                r.get("job_id"),
                r["camera_id"],
                r["timestamp"] if isinstance(r["timestamp"], str) else r["timestamp"].isoformat(),
                r.get("area_px2", 0.0),
                r.get("delta_area_px2", 0.0),
                r.get("dt_seconds", 0.0),
                r.get("growth_rate_px2_per_sec", 0.0),
                r.get("smoothed_growth_rate", 0.0),
                r.get("trend", "UNKNOWN"),
                r.get("confidence", 0.0),
                r.get("created_at", now),
            )
            for r in records
        ]
        with db_transaction() as conn:
            conn.executemany(sql, rows)

    def list_by_job(self, job_id: str) -> list[dict[str, Any]]:
        sql = "SELECT * FROM temporal_analyses WHERE job_id = ? ORDER BY timestamp ASC;"
        with db_transaction() as conn:
            rows = conn.execute(sql, (job_id,)).fetchall()
            return [dict(r) for r in rows]


class SQLiteRiskEventRepository:
    """Repository for spatial risk assessment events and snapshots."""

    def save(self, r: dict[str, Any]) -> None:
        sql = """
        INSERT INTO risk_events (
            snapshot_id, job_id, building_id, floor_id, timestamp,
            global_risk_level, node_risks_json, active_hazards_count, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(snapshot_id) DO NOTHING;
        """
        now = datetime.now(timezone.utc).isoformat()
        node_risks_str = json.dumps(r["node_risks"]) if isinstance(r.get("node_risks"), dict) else r.get("node_risks_json", "{}")
        with db_transaction() as conn:
            conn.execute(
                sql,
                (
                    r["snapshot_id"],
                    r.get("job_id"),
                    r["building_id"],
                    r["floor_id"],
                    r["timestamp"] if isinstance(r["timestamp"], str) else r["timestamp"].isoformat(),
                    r.get("global_risk_level", "LOW"),
                    node_risks_str,
                    r.get("active_hazards_count", 0),
                    r.get("created_at", now),
                ),
            )

    def list_by_job(self, job_id: str) -> list[dict[str, Any]]:
        sql = "SELECT * FROM risk_events WHERE job_id = ? ORDER BY timestamp ASC;"
        with db_transaction() as conn:
            rows = conn.execute(sql, (job_id,)).fetchall()
            return [dict(r) for r in rows]

    def get_latest(self, building_id: str = "bldg-hq-01") -> Optional[dict[str, Any]]:
        sql = "SELECT * FROM risk_events WHERE building_id = ? ORDER BY timestamp DESC LIMIT 1;"
        with db_transaction() as conn:
            row = conn.execute(sql, (building_id,)).fetchone()
            return dict(row) if row else None