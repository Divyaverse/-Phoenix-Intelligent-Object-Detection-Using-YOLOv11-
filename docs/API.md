# PHOENIX REST & WebSocket API Specification

## 1. REST Endpoints (`/api/v1`)

### Authentication (`/auth`)
- `POST /api/v1/auth/login` &rarr; Authenticate user, return JWT access token and user role.
- `GET /api/v1/auth/me` &rarr; Return profile of current authenticated user.

### Incidents (`/incidents`)
- `GET /api/v1/incidents/current` &rarr; Active emergency incidents for authenticated scope.
- `GET /api/v1/incidents/{incident_id}` &rarr; Incident details, timeline, and affected areas.
- `POST /api/v1/incidents` &rarr; Create or declare new incident.

### Evacuation Routes (`/routes`)
- `GET /api/v1/routes/current` &rarr; Current recommended evacuation routes with full cost breakdowns and ETAs.
- `POST /api/v1/routes/compute` &rarr; On-demand route computation between origin and destination nodes.

### Buildings & Floorplans (`/buildings`)
- `GET /api/v1/buildings` &rarr; List accessible buildings.
- `GET /api/v1/buildings/{building_id}` &rarr; Building structure, floors, and navigation graph nodes/edges.
- `GET /api/v1/buildings/{building_id}/floors/{floor_id}/risk` &rarr; Current spatial risk snapshot and heatmap data.

### Cameras & Calibration (`/cameras`)
- `GET /api/v1/cameras` &rarr; List cameras with online status, monitored zones, and calibration state.
- `GET /api/v1/cameras/{camera_id}/calibration` &rarr; Calibration matrix and ground-truth points.

### System Health & Observability (`/system`)
- `GET /api/v1/system/health` &rarr; Liveness probe and subsystem status.
- `GET /api/v1/system/ready` &rarr; Readiness probe checking AI model, database, and navigation graph.

---

## 2. WebSocket Realtime Contract

### Endpoint
- `/ws/v1/buildings/{building_id}?token={jwt_token}`

### Realtime Event Envelope
```json
{
  "event_id": "evt_01h8x9p3...",
  "event_type": "RISK_UPDATED",
  "sequence": 42,
  "timestamp": "2026-09-21T11:25:00.123Z",
  "scope": {
    "organization_id": "org_default",
    "building_id": "bld_main",
    "floor_id": "fl_01"
  },
  "payload": {
    "incident_id": "inc_001",
    "risk_level": "CRITICAL",
    "affected_nodes": ["node_corridor_2", "node_corridor_3"],
    "route_update_required": true
  }
}
```

### Event Types
- `DETECTION_OBSERVED`
- `SMOKE_GROWTH_ALERT`
- `RISK_UPDATED`
- `ROUTE_CHANGED`
- `CAMERA_STATUS_CHANGED`
- `INCIDENT_STATUS_CHANGED`
- `SYSTEM_ALERT`
