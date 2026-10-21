# PHOENIX Backend End-to-End & Contract Freeze Document

## 1. System Overview & End-to-End Pipeline
PHOENIX is a deterministic, AI-driven emergency decision support system. The end-to-end backend flow has been validated across all 13 completion phases:

```
Video/Camera Stream (VideoFrameSource)
      ↓
Dual YOLO Models (fire_smoke_best.pt + yolo11n.pt via YOLOAdapter)
      ↓
Structured Detection Domain Objects (fire, smoke, person)
      ↓
Temporal Smoke Growth Analyzer (TemporalSmokeAnalyzer - EMA smoothing)
      ↓
Planar Homography Mapper (PlanarHomographyMapper - 3x3 RANSAC)
      ↓
Deterministic Risk Engine (DeterministicRiskEngine - exponential spatial decay)
      ↓
Occupancy & Predictive Corridor Blockage (ApproximateOccupancyEstimator & PredictiveBlockageEngine)
      ↓
Deterministic Multi-Factor Evacuation Routing (MultiFactorRoutingEngine - Dijkstra/A*)
      ↓
ETA Travel Time Estimator (DeterministicETAEstimator)
      ↓
SQLite Database Repositories & In-Memory Event Bus (EventBus & WebSocket)
      ↓
FastAPI REST API & Scoped Realtime WebSocket (/ws/v1/buildings/{building_id})
```

---

## 2. API Contract Specification

Base path: `/api/v1`

### Authentication Endpoints
- **`POST /api/v1/auth/login`**
  - **Request**: `LoginRequest` (`email`, `password`)
  - **Response**: `TokenResponse` (`access_token`, `token_type`, `user_id`, `role`, `organization_id`, `expires_in_seconds`)
  - **RBAC**: Public.

### System & Readiness Endpoints
- **`GET /api/v1/system/health`**
  - **Response**: `HealthCheckResponse` (`status`, `timestamp`, `version`, `environment`, `services`)
  - **RBAC**: Public.
- **`GET /api/v1/system/ready`**
  - **Response**: `ReadinessResponse` (`ready`, `ai_status`, `persistence_status`, `timestamp`)
  - **RBAC**: Public.

### Domain Intelligence Endpoints
- **`GET /api/v1/incidents/current?building_id={id}`**
  - **Response**: `IncidentResponse` (`incident_id`, `organization_id`, `building_id`, `floor_id`, `status`, `severity`, `title`, `description`, `hazard_origin_node`, `affected_nodes`, `declared_at`, `updated_at`, `resolved_at`)
  - **RBAC**: Authenticated Users (`SUPERADMIN`, `BUILDING_MANAGER`, `FIRST_RESPONDER`, `OCCUPANT`).
  - **Source**: `SQLiteIncidentRepository` with fallback to default active incident.
- **`GET /api/v1/routes/current?origin={node}&building_id={id}`**
  - **Response**: `RouteRecommendationResponse` (`route_id`, `building_id`, `floor_id`, `origin_node`, `destination_node`, `path_nodes`, `path_edges`, `status`, `eta_seconds`, `total_cost`, `cost_breakdown`, `algorithm_version`, `is_degraded`, `computed_at`)
  - **RBAC**: Authenticated Users.
  - **Source**: `SQLiteRouteRecommendationRepository` with fallback to default route.
- **`GET /api/v1/buildings/{building_id}`**
  - **Response**: `BuildingResponse` (`building_id`, `organization_id`, `name`, `address`, `floors`)
  - **RBAC**: Authenticated Users.
  - **Source**: `SQLiteBuildingRepository`.
- **`GET /api/v1/cameras?building_id={id}`**
  - **Response**: `list[CameraResponse]` (`camera_id`, `organization_id`, `building_id`, `floor_id`, `name`, `source_uri`, `status`, `monitored_nodes`, `has_calibration`, `last_seen_at`)
  - **RBAC**: Authorized Roles (`SUPERADMIN`, `BUILDING_MANAGER`, `FIRST_RESPONDER`).
  - **Source**: `SQLiteCameraRepository`.

---

## 3. Realtime WebSocket Contract Specification

- **Endpoint Path**: `ws://<host>:<port>/ws/v1/buildings/{building_id}?token={jwt_token}`
- **Heartbeat**: Client sends `"ping"`, server responds `{"type": "pong"}`.
- **Envelope Structure**:
  ```json
  {
    "event_id": "evt_abc123",
    "event_type": "RISK_UPDATED",
    "sequence": 42,
    "timestamp": "2026-09-29T13:45:00Z",
    "scope": { "building_id": "bldg-hq-01" },
    "payload": { ... }
  }
  ```

---

## 4. Test Suite Summary
Executed full test suite:
`python -m pytest tests/unit/test_perception.py tests/unit/test_temporal.py tests/unit/test_phase4_phase5_spatial_risk.py tests/unit/test_phase6_phase7_routing_prediction.py tests/unit/test_persistence.py tests/unit/test_realtime.py tests/unit/test_security.py tests/integration/test_pipeline_e2e.py`

**Result**: **32 / 32 PASSED** (3.59s)

---

## 5. Backend Status
**READY FOR FRONTEND INTEGRATION**
