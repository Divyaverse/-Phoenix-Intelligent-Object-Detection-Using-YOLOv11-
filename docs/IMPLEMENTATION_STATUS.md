# PHOENIX Implementation Status Matrix

> **Disclaimer**: PHOENIX (Predictive Heat Observation and Emergency Navigation Intelligence System) is an AI-based emergency decision-support prototype. It is **NOT** a certified life-safety system, a replacement for fire alarms or emergency procedures, a replacement for trained responders, or a system that guarantees safe evacuation.

## Baseline Status vs. PRD Requirements

| Component | PRD Requirement | Implementation File(s) | Status |
| :--- | :--- | :--- | :--- |
| **Perception / YOLO Detection** | FR-005 (P0): Ingest video/frames, detect fire, smoke, and persons; confidence filtering; structured output. | [`app/perception/frame_source.py`](file:///c:/Phoniex/app/perception/frame_source.py), [`app/perception/detector.py`](file:///c:/Phoniex/app/perception/detector.py) | **IMPLEMENTED** |
| **Temporal Analysis** | FR-006 (P1): Maintain smoke-region history; compute smoke-region growth rate ($\Delta \text{area} / \Delta t$); handle noise/missing frames. | [`app/perception/temporal.py`](file:///c:/Phoniex/app/perception/temporal.py) | **IMPLEMENTED** |
| **Spatial Mapping / Homography** | FR-007 (P0): Camera-specific calibration matrix; point projection from image to floorplan coordinates; validity checking. | [`app/spatial/homography.py`](file:///c:/Phoniex/app/spatial/homography.py), [`app/spatial/calibration.py`](file:///c:/Phoniex/app/spatial/calibration.py) | **IMPLEMENTED** |
| **Risk Engine & Dynamic Heatmap** | FR-008 (P0): Deterministic risk scoring combining fire, smoke, temporal growth, occupancy, and proximity. Dynamic floor risk grid/heatmap. | [`app/decision/risk.py`](file:///c:/Phoniex/app/decision/risk.py), [`app/spatial/heatmap.py`](file:///c:/Phoniex/app/spatial/heatmap.py) | **IMPLEMENTED** |
| **Occupancy Estimation** | FR-011 (P1): Approximate person count from detections per zone/corridor. Explicitly labeled as approximate. | [`app/decision/occupancy.py`](file:///c:/Phoniex/app/decision/occupancy.py) | **IMPLEMENTED** |
| **Predictive Blockage Engine** | FR-010 (P1): Score potential corridor blockage based on temporal smoke growth and proximity. | [`app/decision/prediction.py`](file:///c:/Phoniex/app/decision/prediction.py) | **IMPLEMENTED** |
| **Dynamic Routing (NetworkX)** | FR-009 (P0): Deterministic graph-based routing (Dijkstra/A*); configurable cost ($w_d, w_h, w_o, w_p$); edge blocking; NO_VALID_ROUTE / NO_VALID_EXIT handling. | [`app/graph/navigation_graph.py`](file:///c:/Phoniex/app/graph/navigation_graph.py), [`app/decision/routing.py`](file:///c:/Phoniex/app/decision/routing.py) | **IMPLEMENTED** |
| **ETA Estimation** | FR-012 (P1): Deterministic ETA estimation with documented assumptions (distance, walk speed, stairs, congestion factor). | [`app/decision/eta.py`](file:///c:/Phoniex/app/decision/eta.py) | **IMPLEMENTED** |
| **FastAPI REST API** | FR-001, FR-003, FR-004, FR-013 (P0): REST endpoints for auth, incidents, routes, buildings, cameras, health/ready. Versioned schemas. | [`app/api/`](file:///c:/Phoniex/app/api), [`app/main.py`](file:///c:/Phoniex/app/main.py) | **IMPLEMENTED** |
| **WebSocket Realtime Transport** | FR-014 (P0): Dedicated realtime transport using domain event envelopes with sequence numbers and scope. | [`app/events/bus.py`](file:///c:/Phoniex/app/events/bus.py), [`app/events/websocket_router.py`](file:///c:/Phoniex/app/events/websocket_router.py) | **IMPLEMENTED** |
| **SQLite Persistence & Repositories** | FR-013, FR-015 (P0): Repository interfaces, SQLite adapters, atomic transactions, idempotency keys, explicit persistence failure. | [`app/db/sqlite.py`](file:///c:/Phoniex/app/db/sqlite.py), [`app/db/repositories.py`](file:///c:/Phoniex/app/db/repositories.py) | **IMPLEMENTED** |
| **Security & RBAC** | FR-001, FR-002 (P0): JWT auth, password hashing, 4 roles (SuperAdmin, BuildingManager, FirstResponder, Occupant), tenant isolation. | [`app/core/security.py`](file:///c:/Phoniex/app/core/security.py), [`app/api/dependencies.py`](file:///c:/Phoniex/app/api/dependencies.py) | **IMPLEMENTED** |
| **Role-specific Streamlit Dashboard** | 7.6 (P1): Streamlit dashboard with tailored views for SuperAdmin, Building Manager, First Responder, and Occupant. | [`dashboard/app.py`](file:///c:/Phoniex/dashboard/app.py), [`dashboard/api_client.py`](file:///c:/Phoniex/dashboard/api_client.py) | **IMPLEMENTED** |
| **Audit Logging & Observability** | FR-015 (P0): Audit trail for route decisions, structured logging, latency metrics, freshness tracking. | [`app/core/logging.py`](file:///c:/Phoniex/app/core/logging.py) | **IMPLEMENTED** |
| **Evaluation Scenarios** | Section 18: Reproducible benchmarks comparing Static vs Reactive vs Predictive routing across travel cost, reroutes, and latency. | `scenarios/` | **PLANNED** &rarr; Phase 10: Evaluation |

## Phase Milestone Progress
- [x] **PHASE 0 — Repository Bootstrap** (Structure, environment, config, documentation)
- [x] **PHASE 1 — Foundation & Contracts** (Domain models, enums, interfaces, error hierarchy)
- [x] **PHASE 2 — Core AI & Decision Intelligence Engine** (Perception, temporal tracking, homography, risk scoring, NetworkX routing, ETA)
- [x] **PHASE 3 — FastAPI Platform & Schemas**
- [x] **PHASE 6 — SQLite Persistence & Repositories**
- [x] **PHASE 4 — Role-Specific Streamlit Dashboard**
- [x] **PHASE 5 — Realtime WebSocket Broadcast Bus**
- [x] **PHASE 7 — Security & RBAC Enforcement**
- [x] **PHASE 8 — End-to-End Testing & Failure Suites**
- [x] **PHASE 9 — Observability & Freshness Metrics**
- [ ] **PHASE 10 — Evaluation Scenarios (Static vs Reactive vs Predictive)**
