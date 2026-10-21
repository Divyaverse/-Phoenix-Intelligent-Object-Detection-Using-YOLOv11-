"""
Continuous Live Perception & Decision Loop for PHOENIX.
Processes simulated CCTV video feeds frame-by-frame, performs dual-model YOLO detection,
evaluates temporal smoke growth, maps floorplan coordinates, computes risk & evacuation routes,
persists active state to SQLite, and broadcasts real-time domain events over WebSocket EventBus.
"""

import asyncio
from datetime import datetime, timezone
import logging
from typing import Optional

from app.core.config import settings
from app.db.repositories import (
    SQLiteAuditEventRepository,
    SQLiteBuildingRepository,
    SQLiteCameraRepository,
    SQLiteDetectionRepository,
    SQLiteFloorRepository,
    SQLiteFloorplanRepository,
    SQLiteIncidentRepository,
    SQLiteOrganizationRepository,
    SQLiteRouteRecommendationRepository,
)
from app.decision.eta import DeterministicETAEstimator
from app.decision.occupancy import ApproximateOccupancyEstimator
from app.decision.prediction import PredictiveBlockageEngine
from app.decision.risk import DeterministicRiskEngine
from app.decision.routing import MultiFactorRoutingEngine
from app.domain.enums import (
    CameraStatus,
    DetectionType,
    EventType,
    IncidentSeverity,
    IncidentStatus,
    RiskLevel,
    RouteStatus,
)
from app.domain.events import DomainEvent
from app.domain.models import (
    AuditEvent,
    Building,
    CalibrationPoint,
    Camera,
    Floor,
    FloorplanModel,
    Incident,
    NavigationEdge,
    NavigationNode,
    Organization,
    Point2D,
    RouteRecommendation,
    ScaleReference,
)
from app.events.bus import event_bus
from app.events.websocket_router import ws_manager
from app.graph.navigation_graph import NavigationGraph
from app.perception.detector import YOLOAdapter
from app.perception.frame_source import VideoFrameSource
from app.perception.temporal import TemporalSmokeAnalyzer
from app.spatial.calibration import CalibrationService
from app.spatial.floorplan_parser import FloorplanProcessor
from app.spatial.homography import PlanarHomographyMapper
from app.spatial.spatial_manager import spatial_manager
from app.spatial.video_geometry import VideoGeometryExtractor

logger = logging.getLogger("phoenix.perception")


class ContinuousPerceptionPipeline:
    """
    Manages continuous video frame ingestion and end-to-end emergency intelligence.
    """

    def __init__(
        self,
        building_id: str = "bldg-hq-01",
        floor_id: str = "fl-01",
        primary_video_path: Optional[str] = None,
        primary_camera_id: Optional[str] = None,
    ) -> None:
        self.building_id = building_id
        self.floor_id = floor_id
        self.primary_video_path = primary_video_path or getattr(settings.perception, "video_source_path", "videos/test2.mp4")
        self.primary_camera_id = primary_camera_id or getattr(settings.perception, "primary_camera_id", "CAM-SOUTH-01")

        self.running = False
        self._task: Optional[asyncio.Task] = None

        # Core engines
        self.detector = YOLOAdapter(
            fire_smoke_model_path="models/fire_smoke_best.pt",
            person_model_path="models/yolo11n.pt",
        )
        self.temporal_analyzer = TemporalSmokeAnalyzer()
        self.homography_mapper = PlanarHomographyMapper()
        self.cal_service = CalibrationService(mapper=self.homography_mapper)
        self.fp_processor = FloorplanProcessor()
        self.geometry_extractor = VideoGeometryExtractor(homography_mapper=self.homography_mapper)
        self.spatial_mgr = spatial_manager
        self.risk_engine = DeterministicRiskEngine()
        self.occupancy_estimator = ApproximateOccupancyEstimator()
        self.prediction_engine = PredictiveBlockageEngine()
        self.routing_engine = MultiFactorRoutingEngine()
        self.eta_estimator = DeterministicETAEstimator()

        # Repositories
        self.org_repo = SQLiteOrganizationRepository()
        self.incident_repo = SQLiteIncidentRepository()
        self.route_repo = SQLiteRouteRecommendationRepository()
        self.building_repo = SQLiteBuildingRepository()
        self.floor_repo = SQLiteFloorRepository()
        self.camera_repo = SQLiteCameraRepository()
        self.floorplan_repo = SQLiteFloorplanRepository()
        self.detection_repo = SQLiteDetectionRepository()
        self.audit_repo = SQLiteAuditEventRepository()

        # State tracking
        self.active_incident: Optional[Incident] = None
        self.latest_route: Optional[RouteRecommendation] = None
        self.frame_source: Optional[VideoFrameSource] = None
        self.calibration = None
        self.nav_graph: Optional[NavigationGraph] = None
        self.floorplan: Optional[FloorplanModel] = None

    def initialize_environment(self) -> None:
        """Seed building layout, topology, and calibration in database."""
        # Organization
        org = Organization(
            organization_id="org-phoenix-main",
            name="Phoenix Main Organization",
        )
        self.org_repo.save(org)

        # Building
        bldg = Building(
            building_id=self.building_id,
            organization_id="org-phoenix-main",
            name="Phoenix Innovation Center",
            address="100 Tech Blvd, Building A",
        )
        self.building_repo.save(bldg)

        # Floor
        fl = Floor(
            floor_id=self.floor_id,
            building_id=self.building_id,
            floor_number=1,
            name="Ground Floor Main Lobby",
            width_meters=50.0,
            height_meters=40.0,
        )
        self.floor_repo.save(fl)

        # Cameras
        cams = [
            Camera(
                camera_id="CAM-MAIN-01",
                organization_id="org-phoenix-main",
                building_id=self.building_id,
                floor_id=self.floor_id,
                name="Central Corridor North View (Main CCTV)",
                source_uri="/videos/Main_video.mp4",
                status=CameraStatus.ONLINE,
                monitored_nodes=["node_corridor_mid", "node_east_alcove", "node_corridor_north"],
            ),
            Camera(
                camera_id="CAM-MAIN-01-AI",
                organization_id="org-phoenix-main",
                building_id=self.building_id,
                floor_id=self.floor_id,
                name="Central Corridor (AI Detection Overlay)",
                source_uri="/videos/Main_video_annotated.mp4",
                status=CameraStatus.ONLINE,
                monitored_nodes=["node_corridor_mid", "node_east_alcove"],
            ),
            Camera(
                camera_id="CAM-NORTH-01",
                organization_id="org-phoenix-main",
                building_id=self.building_id,
                floor_id=self.floor_id,
                name="North Corridor",
                source_uri="/videos/test 1.mp4",
                status=CameraStatus.ONLINE,
                monitored_nodes=["node_corridor_north", "exit_north"],
            ),
            Camera(
                camera_id="CAM-SOUTH-01",
                organization_id="org-phoenix-main",
                building_id=self.building_id,
                floor_id=self.floor_id,
                name="South Exit Corridor",
                source_uri="/videos/test2.mp4",
                status=CameraStatus.ONLINE,
                monitored_nodes=["node_corridor_south", "exit_south"],
            ),
            Camera(
                camera_id="CAM-UPLOAD",
                organization_id="org-phoenix-main",
                building_id=self.building_id,
                floor_id=self.floor_id,
                name="Uploaded Video Stream (Uncalibrated)",
                source_uri="/videos/uploaded",
                status=CameraStatus.ONLINE,
                monitored_nodes=[],
            ),
        ]
        for c in cams:
            self.camera_repo.save(c)

        # Dynamic Floorplan Model & Navigation Graph
        is_main_video = "main_video" in self.primary_video_path.lower()
        db_fp = self.floorplan_repo.get_by_floor(self.building_id, self.floor_id)
        if is_main_video:
            if not db_fp or getattr(db_fp, "name", "") != "Corporate Central Corridor & Offices (Main CCTV View)":
                db_fp = self.fp_processor.create_main_corridor_floorplan(
                    building_id=self.building_id,
                    floor_id=self.floor_id,
                )
                self.floorplan_repo.save(db_fp)
        else:
            if not db_fp or "Main CCTV" in getattr(db_fp, "name", ""):
                db_fp = self.fp_processor.create_synthetic_architectural_floorplan(
                    building_id=self.building_id,
                    floor_id=self.floor_id,
                    name="Ground Floor Layout",
                )
                self.floorplan_repo.save(db_fp)

        self.floorplan = db_fp
        self.spatial_mgr.register_floorplan(db_fp)
        self.nav_graph = self.spatial_mgr.get_navigation_graph(self.building_id, self.floor_id)

        # Ground-Plane Homography calibration for primary camera
        if is_main_video:
            cal_points = [
                CalibrationPoint(image_point=Point2D(x=280.0, y=700.0), floor_point=Point2D(x=14.0, y=5.0)),
                CalibrationPoint(image_point=Point2D(x=820.0, y=700.0), floor_point=Point2D(x=18.0, y=5.0)),
                CalibrationPoint(image_point=Point2D(x=425.0, y=475.0), floor_point=Point2D(x=14.0, y=20.0)),
                CalibrationPoint(image_point=Point2D(x=575.0, y=475.0), floor_point=Point2D(x=18.0, y=20.0)),
            ]
        else:
            cal_points = [
                CalibrationPoint(image_point=Point2D(x=0.0, y=0.0), floor_point=Point2D(x=0.0, y=0.0)),
                CalibrationPoint(image_point=Point2D(x=3840.0, y=0.0), floor_point=Point2D(x=50.0, y=0.0)),
                CalibrationPoint(image_point=Point2D(x=3840.0, y=2160.0), floor_point=Point2D(x=50.0, y=40.0)),
                CalibrationPoint(image_point=Point2D(x=0.0, y=2160.0), floor_point=Point2D(x=0.0, y=40.0)),
            ]
        self.calibration = self.cal_service.create_calibration(
            self.primary_camera_id, self.building_id, self.floor_id, cal_points
        )
        self.spatial_mgr.register_camera_calibration(self.calibration)

        self.frame_source = VideoFrameSource(self.primary_video_path, target_fps=5.0, loop=True)

    async def start(self) -> None:
        """Start the background perception worker."""
        if self.running:
            return
        self.running = True
        self.initialize_environment()
        self._task = asyncio.create_task(self._perception_loop())
        logger.info("Continuous Perception Pipeline started.")


    async def stop(self) -> None:
        """Stop background worker and release resources."""
        self.running = False
        if self._task:
            self._task.cancel()
        if self.frame_source:
            self.frame_source.release()
        logger.info("Continuous Perception Pipeline stopped.")

    async def _perception_loop(self) -> None:
        """Continuous frame ingestion, inference, risk evaluation, and event dispatch."""
        while self.running:
            try:
                if not self.frame_source or not self.frame_source.is_opened():
                    await asyncio.sleep(1.0)
                    continue

                success, frame, ts = self.frame_source.read_frame()
                if not success or frame is None:
                    await asyncio.sleep(0.2)
                    continue

                frame_id = f"f_{self.frame_source.get_frame_count():05d}"

                # 1. Run dual-model YOLO inference
                detections = self.detector.detect(
                    frame=frame,
                    frame_id=frame_id,
                    camera_id=self.primary_camera_id,
                    timestamp_seconds=ts,
                )

                # 2. Project spatial coordinates via Homography
                for det in detections:
                    if self.calibration:
                        det.floor_point = self.homography_mapper.image_to_floorplan(
                            det.bbox.ground_point, self.calibration
                        )

                # Persist real-time detections batch to SQLite
                if detections:
                    self.detection_repo.save_batch(detections)

                    # Broadcast DETECTION_OBSERVED domain event over WebSocket
                    scope = {"building_id": self.building_id, "camera_id": self.primary_camera_id}
                    det_event = DomainEvent(
                        event_type=EventType.DETECTION_OBSERVED,
                        payload={
                            "camera_id": self.primary_camera_id,
                            "frame_id": frame_id,
                            "detections": [
                                {
                                    "class_name": d.class_name.value,
                                    "confidence": round(d.confidence, 3),
                                    "bbox": {"x1": round(d.bbox.x1, 1), "y1": round(d.bbox.y1, 1), "x2": round(d.bbox.x2, 1), "y2": round(d.bbox.y2, 1)},
                                    "floor_point": {"x": round(d.floor_point.x, 2), "y": round(d.floor_point.y, 2)} if d.floor_point else None,
                                }
                                for d in detections
                            ],
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                        },
                    )
                    envelope = await event_bus.publish(det_event, scope)
                    await ws_manager.broadcast_to_building(self.building_id, envelope)

                # 3. Temporal smoke analysis
                smoke_obs = self.temporal_analyzer.process_observations(
                    self.primary_camera_id, detections, ts
                )
                smoke_observations = [smoke_obs] if smoke_obs else []

                if smoke_obs:
                    # Broadcast SMOKE_GROWTH_ALERT domain event over WebSocket
                    scope = {"building_id": self.building_id, "camera_id": self.primary_camera_id}
                    smoke_event = DomainEvent(
                        event_type=EventType.SMOKE_GROWTH_ALERT,
                        payload={
                            "camera_id": self.primary_camera_id,
                            "area_px2": round(smoke_obs.area_px2, 1),
                            "growth_rate_px2_per_sec": round(smoke_obs.smoothed_growth_rate or smoke_obs.growth_rate_px2_per_sec, 2),
                            "trend": smoke_obs.trend.value,
                            "confidence": round(smoke_obs.confidence, 3),
                            "timestamp": smoke_obs.timestamp.isoformat(),
                        },
                    )
                    envelope = await event_bus.publish(smoke_event, scope)
                    await ws_manager.broadcast_to_building(self.building_id, envelope)

                # 4. Filter for fire/smoke hazards
                hazard_dets = [
                    d for d in detections if d.class_name in (DetectionType.FIRE, DetectionType.SMOKE)
                ]

                # Check if hazard detected
                if hazard_dets:
                    self._clear_frames_count = 0
                    if not self.active_incident:
                        # Trigger new genuine incident from actual YOLO detection
                        hazard_type = hazard_dets[0].class_name.value.upper()
                        cam = self.camera_repo.get(self.primary_camera_id)
                        cam_name = cam.name if cam else "Central Corridor"
                        hazard_origin = cam.monitored_nodes[1] if (cam and len(cam.monitored_nodes) > 1) else (cam.monitored_nodes[0] if cam and cam.monitored_nodes else "node_east_alcove")
                        affected = cam.monitored_nodes if cam and cam.monitored_nodes else ["node_east_alcove", "node_corridor_mid"]

                        self.active_incident = Incident(
                            incident_id=f"INC-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
                            organization_id="org-phoenix-main",
                            building_id=self.building_id,
                            floor_id=self.floor_id,
                            status=IncidentStatus.CONFIRMED,
                            severity=IncidentSeverity.HIGH,
                            title=f"Detected {hazard_type} in {cam_name}",
                            description=f"Automated YOLO perception detected {hazard_type} on {cam_name} with confidence {hazard_dets[0].confidence:.2f}.",
                            hazard_origin_node=hazard_origin,
                            affected_nodes=affected,
                            declared_at=datetime.now(timezone.utc),
                            updated_at=datetime.now(timezone.utc),
                        )
                        self.incident_repo.save(self.active_incident)

                        # Record immutable audit trail event in SQLite
                        audit_decl = AuditEvent(
                            audit_id=f"AUD-{self.active_incident.incident_id}-DECL",
                            timestamp=self.active_incident.declared_at,
                            organization_id=self.active_incident.organization_id,
                            action="INCIDENT_DECLARED",
                            entity_type="Incident",
                            entity_id=self.active_incident.incident_id,
                            after_state={"severity": self.active_incident.severity.value, "title": self.active_incident.title},
                            reason=self.active_incident.description,
                        )
                        self.audit_repo.record_event(audit_decl, idempotency_key=f"idemp-{self.active_incident.incident_id}-decl")


                        # Calculate Risk, Occupancy, Blockage Prediction & Multi-Factor Route
                        if self.nav_graph:
                            all_nodes = self.nav_graph.get_all_nodes()
                            all_edges = self.nav_graph.get_all_edges()
                            nodes_dict = {n.node_id: n for n in all_nodes}

                            # 1. Deterministic Spatial Risk
                            risk_snapshot = self.risk_engine.calculate_risk(
                                self.building_id,
                                self.floor_id,
                                all_nodes,
                                detections,
                                smoke_observations,
                            )

                            # Broadcast RISK_UPDATED over WebSocket
                            scope = {"building_id": self.building_id}
                            risk_evt = DomainEvent(
                                event_type=EventType.RISK_UPDATED,
                                payload={
                                    "building_id": self.building_id,
                                    "floor_id": self.floor_id,
                                    "global_risk_level": risk_snapshot.global_risk_level.value,
                                    "node_risks": {k: round(v, 3) for k, v in risk_snapshot.node_risks.items()},
                                    "active_hazards_count": risk_snapshot.active_hazards_count,
                                    "timestamp": risk_snapshot.timestamp.isoformat(),
                                },
                            )
                            r_env = await event_bus.publish(risk_evt, scope)
                            await ws_manager.broadcast_to_building(self.building_id, r_env)

                            # 2. Live Occupancy from current person detections
                            occupancy_map = self.occupancy_estimator.estimate_node_occupancies(
                                all_nodes,
                                detections,
                            )

                            # 3. Live Predicted Corridor Blockage from temporal smoke growth
                            blockage_predictions = self.prediction_engine.predict_blockage_scores(
                                all_edges,
                                nodes_dict,
                                smoke_observations,
                            )

                            # 4. Multi-Factor Route Optimization
                            nav_origin = "node_west_suites" if "node_west_suites" in nodes_dict else ("room_101" if "room_101" in nodes_dict else [n.node_id for n in all_nodes if not n.is_exit][0])
                            route = self.routing_engine.compute_route(
                                nodes=all_nodes,
                                edges=all_edges,
                                origin_node_id=nav_origin,
                                destination_exit_ids=self.nav_graph.get_exit_node_ids(),
                                risk_snapshot=risk_snapshot,
                                occupancy_map=occupancy_map,
                                blockage_predictions=blockage_predictions,
                            )
                            path_nodes = [self.nav_graph.get_node(nid) for nid in route.path_nodes if self.nav_graph.get_node(nid)]
                            path_edges = [e for e in all_edges if e.edge_id in route.path_edges]
                            route.eta_seconds = self.eta_estimator.calculate_eta(path_nodes, path_edges, occupancy_map, risk_snapshot)

                            self.latest_route = route
                            self.route_repo.save(route)

                        # Broadcast INCIDENT_STATUS_CHANGED event over WebSocket
                        scope = {"building_id": self.building_id}
                        event = DomainEvent(
                            event_type=EventType.INCIDENT_STATUS_CHANGED,
                            payload={
                                "incident_id": self.active_incident.incident_id,
                                "status": self.active_incident.status.value,
                                "severity": self.active_incident.severity.value,
                                "title": self.active_incident.title,
                                "hazard_origin_node": self.active_incident.hazard_origin_node,
                                "affected_nodes": self.active_incident.affected_nodes,
                                "declared_at": self.active_incident.declared_at.isoformat(),
                            },
                        )
                        envelope = await event_bus.publish(event, scope)
                        await ws_manager.broadcast_to_building(self.building_id, envelope)
                        logger.info(f"Broadcasted new incident event: {self.active_incident.incident_id}")

                    elif self.active_incident and self.nav_graph:
                        # Update risk, occupancy, predicted blockage and route dynamically
                        all_nodes = self.nav_graph.get_all_nodes()
                        all_edges = self.nav_graph.get_all_edges()
                        nodes_dict = {n.node_id: n for n in all_nodes}

                        # 1. Deterministic Spatial Risk
                        risk_snapshot = self.risk_engine.calculate_risk(
                            self.building_id,
                            self.floor_id,
                            all_nodes,
                            detections,
                            smoke_observations,
                        )

                        # Broadcast RISK_UPDATED over WebSocket
                        scope = {"building_id": self.building_id}
                        risk_evt = DomainEvent(
                            event_type=EventType.RISK_UPDATED,
                            payload={
                                "building_id": self.building_id,
                                "floor_id": self.floor_id,
                                "global_risk_level": risk_snapshot.global_risk_level.value,
                                "node_risks": {k: round(v, 3) for k, v in risk_snapshot.node_risks.items()},
                                "active_hazards_count": risk_snapshot.active_hazards_count,
                                "timestamp": risk_snapshot.timestamp.isoformat(),
                            },
                        )
                        r_env = await event_bus.publish(risk_evt, scope)
                        await ws_manager.broadcast_to_building(self.building_id, r_env)

                        # 2. Live Occupancy from current person detections
                        occupancy_map = self.occupancy_estimator.estimate_node_occupancies(
                            all_nodes,
                            detections,
                        )

                        # 3. Live Predicted Corridor Blockage from temporal smoke growth
                        blockage_predictions = self.prediction_engine.predict_blockage_scores(
                            all_edges,
                            nodes_dict,
                            smoke_observations,
                        )

                        # 4. Multi-Factor Route Optimization
                        nav_origin = "node_west_suites" if "node_west_suites" in nodes_dict else ("room_101" if "room_101" in nodes_dict else [n.node_id for n in all_nodes if not n.is_exit][0])
                        route = self.routing_engine.compute_route(
                            nodes=all_nodes,
                            edges=all_edges,
                            origin_node_id=nav_origin,
                            destination_exit_ids=self.nav_graph.get_exit_node_ids(),
                            risk_snapshot=risk_snapshot,
                            occupancy_map=occupancy_map,
                            blockage_predictions=blockage_predictions,
                        )
                        path_nodes = [self.nav_graph.get_node(nid) for nid in route.path_nodes if self.nav_graph.get_node(nid)]
                        path_edges = [e for e in all_edges if e.edge_id in route.path_edges]
                        route.eta_seconds = self.eta_estimator.calculate_eta(path_nodes, path_edges, occupancy_map, risk_snapshot)

                        route_changed = (
                            self.latest_route is None
                            or self.latest_route.path_nodes != route.path_nodes
                            or self.latest_route.destination_node != route.destination_node
                            or abs(self.latest_route.total_cost - route.total_cost) > 0.02
                            or abs(self.latest_route.eta_seconds - route.eta_seconds) > 0.5
                        )

                        self.latest_route = route
                        self.route_repo.save(route)

                        if route_changed:
                            scope = {"building_id": self.building_id}
                            ev_route = DomainEvent(
                                event_type=EventType.ROUTE_CHANGED,
                                payload={
                                    "route_id": route.route_id,
                                    "origin_node": route.origin_node,
                                    "destination_node": route.destination_node,
                                    "path_nodes": route.path_nodes,
                                    "eta_seconds": route.eta_seconds,
                                    "total_cost": route.total_cost,
                                },
                            )
                            envelope = await event_bus.publish(ev_route, scope)
                            await ws_manager.broadcast_to_building(self.building_id, envelope)
                else:
                    # No hazard detections in current frame
                    if self.active_incident:
                        self._clear_frames_count = getattr(self, "_clear_frames_count", 0) + 1
                        # If clear for 30 consecutive perception cycles (~15s), resolve incident
                        if self._clear_frames_count >= 30:
                            self.active_incident.status = IncidentStatus.RESOLVED
                            self.active_incident.resolved_at = datetime.now(timezone.utc)
                            self.incident_repo.save(self.active_incident)

                            # Record resolution audit event in SQLite
                            audit_res = AuditEvent(
                                audit_id=f"AUD-{self.active_incident.incident_id}-RES",
                                timestamp=self.active_incident.resolved_at,
                                organization_id=self.active_incident.organization_id,
                                action="INCIDENT_RESOLVED",
                                entity_type="Incident",
                                entity_id=self.active_incident.incident_id,
                                after_state={"status": IncidentStatus.RESOLVED.value},
                                reason="Hazard cleared from perception feed",
                            )
                            self.audit_repo.record_event(audit_res, idempotency_key=f"idemp-{self.active_incident.incident_id}-res")

                            scope = {"building_id": self.building_id}
                            event = DomainEvent(
                                event_type=EventType.INCIDENT_STATUS_CHANGED,
                                payload={
                                    "incident_id": self.active_incident.incident_id,
                                    "status": IncidentStatus.RESOLVED.value,
                                    "severity": self.active_incident.severity.value,
                                    "title": "Hazard Cleared - Incident Resolved",
                                    "resolved_at": self.active_incident.resolved_at.isoformat(),
                                },
                            )
                            envelope = await event_bus.publish(event, scope)
                            await ws_manager.broadcast_to_building(self.building_id, envelope)
                            logger.info(f"Incident {self.active_incident.incident_id} resolved and closed.")
                            self.active_incident = None
                            self.latest_route = None
                            self._clear_frames_count = 0

                # Regulate processing rate (~2 FPS for perception loop)
                await asyncio.sleep(0.5)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Error in continuous perception loop: {e}", exc_info=True)
                await asyncio.sleep(1.0)


# Global singleton instance
continuous_perception_pipeline = ContinuousPerceptionPipeline()

