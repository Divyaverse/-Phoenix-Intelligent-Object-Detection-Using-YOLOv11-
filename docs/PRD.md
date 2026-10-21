# PHOENIX — Product Requirements Document (PRD)

**Project Name**: PHOENIX (Predictive Heat Observation and Emergency Navigation Intelligence System)  
**Document Version**: 1.0.0  
**Status**: Active / Engineering Prototype Validated  
**Author / Team**: PHOENIX Core Engineering Team  
**Date**: October 2026  

---

## 1. Executive Summary

**PHOENIX** is an AI-powered, real-time emergency decision-support system designed to assist building managers, first responders, and occupants during structural fire emergencies. 

Traditional emergency evacuation systems rely on static exit signs, audible alarms, and fixed evacuation paths that fail to account for dynamic hazard propagation (e.g., rapid smoke spread or corridor blockage). PHOENIX augments emergency awareness by pairing dual-model computer vision (YOLOv11 for fire, smoke, and occupant detection) with temporal expansion modeling ($\Delta\text{area}/\Delta t$), planar homography projection onto 2D floorplans, deterministic spatial risk scoring, and dynamic graph-based routing (NetworkX).

> [!IMPORTANT]
> **Safety Boundary & Disclaimer**:  
> PHOENIX is an AI-based **decision-support prototype**. It is **NOT** a certified life-safety system, not a replacement for standard NFPA/EN54 fire alarm infrastructure, and cannot guarantee safe evacuation. To prevent hallucinations in life-critical contexts, **Large Language Models (LLMs) are strictly barred from computing or altering evacuation routes**. All paths are calculated deterministically using graph algorithms.

---

## 2. Problem Statement & Objectives

### 2.1 The Problem
- **Static Evacuation Failures**: Traditional signage guides building occupants along predetermined paths that may lead directly toward spreading fire or smoke-choked corridors.
- **Blind Navigation for First Responders**: Emergency personnel arrive at facilities without real-time situational awareness regarding occupant locations, fire origin points, or corridor viability.
- **Delayed Threat Recognition**: Dense smoke migration often cuts off primary egress points minutes before open flames appear; without predictive expansion modeling, occupants become trapped in dead ends.

### 2.2 Core Product Objectives
1. **Real-time Hazard Ingestion**: Ingest IP/CCTV video feeds and detect fire, smoke, and occupants with sub-second latency.
2. **Predictive Corridor Blockage**: Compute temporal smoke growth rate ($\Delta\text{area}/\Delta t$) to forecast corridor impassability up to 15–30 seconds before complete blockage.
3. **Deterministic Evacuation Routing**: Dynamically recalculate the safest exit paths using multi-factor penalty scoring without route oscillation or non-existent path generation.
4. **Role-Tailored Situational Dashboards**: Provide real-time operational feeds via WebSockets to Building Managers, Responders, and Occupants.
5. **Fail-Closed Reliability**: Gracefully fall back to degraded modes (`AI_DEGRADED`, `CAMERA_OFFLINE`, `NO_VALID_ROUTE`) when perception or hardware is compromised.

---

## 3. User Personas & Target Audiences

| Persona | Role | Primary Needs | Key Views / Features |
| :--- | :--- | :--- | :--- |
| **SuperAdmin** | Infrastructure & Security Lead | Multi-tenant management, camera calibration, system readiness audits. | System health, tenant config, audit trail, camera homography calibration. |
| **Building Manager** | Facility Operations Manager | Global facility floorplan visibility, sensor health, automated incident declarations. | Real-time hazard heatmap, sensor feed status, manual incident declaration override. |
| **First Responder** | Firefighter / Emergency Crew | Immediate hazard origin identification, headcount estimates per zone, blocked corridor warnings. | Tactical floorplan view, occupant counts by zone, hazard propagation vectors. |
| **Occupant** | Building Tenant / Visitor | Low-cognitive-load, immediate evacuation guidance away from threats with live ETA. | Turn-by-turn evacuation path, nearest safe exit, dynamic reroute alerts. |

---

## 4. System Architecture & Processing Pipeline

```
┌─────────────────────────────────────────────────────────────┐
│                       VIDEO INGESTION                       │
│           RTSP Stream / CCTV / Synthetic Test Feeds         │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                    DUAL-MODEL PERCEPTION                    │
│   • Fire & Smoke: Custom YOLOv11 (fire_smoke_best.pt)       │
│   • Occupant Headcount: Pre-trained YOLOv11 (yolo11n.pt)    │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                      TEMPORAL TRACKING                      │
│   • Exponential Moving Average (EMA) bounding box tracking  │
│   • Smoke Region Expansion Rate (Δarea / Δt)                │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                 PLANAR HOMOGRAPHY PROJECTION                │
│   • 3x3 Calibration Matrix (Camera Pixel Coordinates ->     │
│     Floorplan Metric Plane (x, y))                          │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│             DETERMINISTIC RISK & PREDICTION ENGINE          │
│   • Spatial decay risk grid (Fire=1.0, Smoke=0.6, Proximity)│
│   • Approximate headcount per zone / node                   │
│   • Corridor blockage velocity prediction                   │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│              NETWORKX MULTI-FACTOR ROUTING ENGINE           │
│   • Dynamic edge weights: Distance + Hazard + Occupancy +   │
│     Predicted Blockage Penalty                              │
│   • Deterministic Dijkstra / A* (Fail-closed on exit loss)  │
│   • Deterministic Walking ETA Calculation                   │
└──────────────────────────────┬──────────────────────────────┘
                               │
                               ▼
┌─────────────────────────────────────────────────────────────┐
│                  EVENT DISPATCH & INTERFACES                │
│   • In-Memory Event Bus & WebSocket Broadcast Engine        │
│   • FastAPI REST Services & SQLite Audit Persistence        │
│   • React Web Dashboard + Streamlit Prototyping Console     │
└─────────────────────────────────────────────────────────────┘
```

---

## 5. Functional Requirements (FR)

### 5.1 Perception & Vision Analysis
- **FR-001 [P0] Dual-Model Object Detection**: The system must run inference on video frames to detect `fire`, `smoke`, and `person`. Output must conform to structured domain models containing normalized bounding boxes $[0.0, 1.0]$, confidence scores, and frame metadata.
- **FR-002 [P0] Frame Ingestion**: Support video files (`.mp4`), camera streams, and synthetic benchmark generators with graceful handling of frame drops.
- **FR-003 [P1] Temporal Smoke Growth Estimation**: Compute pixel area delta over time ($\Delta\text{area}/\Delta t$) with exponential smoothing (EMA) to mitigate camera flicker and optical noise.

### 5.2 Spatial Mapping & Risk Modeling
- **FR-004 [P0] Camera Homography Calibration**: Maintain a validated $3 \times 3$ transformation matrix per camera. Reject invalid homographies with an explicit `SPATIAL_MAPPING_UNAVAILABLE` event.
- **FR-005 [P0] Deterministic Risk Scoring**: Calculate local floor hazard scores from fire, smoke, and proximity using exponential spatial decay:
  $$\text{Risk}(x, y) = \sum_i w_i \cdot \exp\left(-\frac{d_i^2}{2\sigma_i^2}\right)$$
- **FR-006 [P1] Occupancy Estimation**: Provide normalized headcount estimates per corridor/room zone, clearly tagged as **approximate**.
- **FR-007 [P1] Predictive Corridor Blockage**: Factor growth vectors into upcoming edge penalties to warn occupants before a hallway becomes impassable.

### 5.3 Routing & Navigation Engine
- **FR-008 [P0] Multi-Factor Dynamic Routing**: Compute paths using NetworkX Dijkstra/A* algorithms with configurable cost weights:
  $$\text{Cost}(e) = w_d \cdot \text{distance} + w_h \cdot \text{hazard} + w_o \cdot \text{occupancy} + w_p \cdot \text{prediction}$$
- **FR-009 [P0] Fail-Closed Safe Handling**: If all exits are blocked or severed, emit an explicit `NO_VALID_ROUTE` / `NO_VALID_EXIT` state. Never hallucinate or synthesize non-existent pathways.
- **FR-010 [P1] Deterministic ETA Calculation**: Calculate expected walking evacuation times using documented walking speed constants ($1.2\text{ m/s}$ base speed), stair traversal penalties ($1.8\times$), and congestion factors.

### 5.4 Backend Services & Security
- **FR-011 [P0] REST API Endpoints**: Expose FastAPI endpoints for authentication, incident management, route querying, building definitions, and health/readiness probes.
- **FR-012 [P0] Real-Time WebSocket Bus**: Broadcast event envelopes (`incident.updated`, `route.recalculated`, `hazard.detected`) scoped by building and floor.
- **FR-013 [P0] Role-Based Access Control (RBAC)**: Enforce JWT authentication with four distinct permission levels: `SuperAdmin`, `BuildingManager`, `FirstResponder`, `Occupant`.
- **FR-014 [P0] Audit Logging & Persistence**: Persist system events, route decisions, and incidents to SQLite with transactional guarantees and structured logging.

### 5.5 Frontends & User Experience
- **FR-015 [P1] Interactive React Application**: Modern single-page React/Vite dashboard displaying dynamic floorplans, real-time heatmaps, live route pathing, and alert banners.
- **FR-016 [P1] Streamlit Diagnostic Console**: Streamlit dashboard for operator triage, model validation, and manual scenario playback.

---

## 6. Non-Functional Requirements (NFR)

| Category | Requirement | Target Metric |
| :--- | :--- | :--- |
| **Latency** | End-to-end perception-to-route recomputation latency | $< 350\text{ ms}$ on GPU / $< 800\text{ ms}$ on CPU |
| **Throughput** | WebSocket message broadcast latency | $< 50\text{ ms}$ fan-out latency |
| **Reliability** | Fail-closed graceful degradation under hardware or model dropout | 100% test coverage on fault paths |
| **Security** | Password hashing (bcrypt) and cryptographic JWT token expiry | Enforced on 100% of non-public endpoints |
| **Data Integrity** | Foreign key constraints and atomic database transactions | Zero orphaned incident or route records |
| **Portability** | Cross-platform containerization and native execution | Docker Compose + Windows / Linux compatibility |

---

## 7. Edge Cases & Degraded Mode Matrix

| Failure Mode | Detection Trigger | Fallback Behavior |
| :--- | :--- | :--- |
| **Camera Disconnect** | FrameSource returns empty/corrupted frames | Emits `CAMERA_OFFLINE`; maintains last valid risk snapshot with explicit freshness degradation. |
| **Model Weight Failure** | Checkpoint missing or GPU OOM | Emits `AI_DEGRADED`; routing falls back to static building geometry distances. |
| **Degraded Calibration** | Homography determinant near singular ($\det(H) \approx 0$) | Emits `SPATIAL_MAPPING_UNAVAILABLE`; suppresses planar projection. |
| **All Exits Engulfed** | Graph search finds zero paths below hazard threshold | Emits `NO_VALID_EXIT`; instructs shelter-in-place at safest available node. |
| **Database Lock** | SQLite disk lock contention during high concurrency | In-memory bus continues real-time WebSocket delivery; logs persistence warning. |

---

## 8. Routing Benchmark Framework: Static vs. Reactive vs. Predictive

PHOENIX includes an automated evaluation benchmark (`scenarios/benchmark.py`) comparing three routing paradigms:

1. **Static Routing**: Standard shortest distance graph traversal (classical building egress).
2. **Reactive Routing**: Evacuation route penalizes active hazard zones only after smoke/fire enters the hallway.
3. **Predictive Routing (PHOENIX)**: Evacuation route penalizes active hazard AND anticipated smoke corridor encroachment based on temporal velocity ($\Delta\text{area}/\Delta t$).

### Evaluation Metrics
- **Cumulative Evacuation Cost / Time**: Normalized travel penalty.
- **Blocked Route Selection Rate**: Frequency with which an occupant is guided into an impassable corridor.
- **Time to First Reroute**: Latency between hazard detection and safe route dispatch.
- **Prediction Lead Time**: Advance warning buffer provided before a corridor becomes completely smoke-filled (Benchmark: $\sim 12\text{ seconds}$ advance warning).

---

## 9. Current Project Implementation Status

```
Component                              Status          Notes
────────────────────────────────────────────────────────────────────────────────
PHASE 0: Repo Bootstrap & Structure    COMPLETED (100%) Modular clean architecture, configs, docs
PHASE 1: Domain Models & Enums         COMPLETED (100%) Pydantic schemas, domain entities, errors
PHASE 2: Perception, Homography & AI   COMPLETED (100%) Dual-YOLO adapter, EMA temporal, 3x3 homography
PHASE 3: FastAPI REST API & Contracts  COMPLETED (100%) Endpoints for auth, routes, incidents, health
PHASE 4: Streamlit Dashboard           COMPLETED (100%) Interactive prototyping dashboard
PHASE 5: WebSocket Real-Time Bus       COMPLETED (100%) EventBus, scoped websockets, live fan-out
PHASE 6: SQLite Persistence & Repos    COMPLETED (100%) Repositories, transactions, audit trail
PHASE 7: Security & RBAC Enforcement   COMPLETED (100%) JWT auth, 4 user roles, tenant isolation
PHASE 8: Test Suite (Unit & E2E)       COMPLETED (100%) 76/76 automated tests passing
PHASE 9: Observability & Diagnostics   COMPLETED (100%) Logging, freshness counters, health checks
PHASE 10: Evaluation & Benchmarking    FUNCTIONAL (90%) Benchmark runner in scenarios/benchmark.py
Frontend: React + Vite Interface       BUILT & READY   TypeScript React dashboard in frontend/
```

### Verification Highlights:
- **Test Suite**: **76 passed in 30.70s** (`pytest` across unit, contract, and integration suites).
- **Dual-Model Perception Report**: 100% verified on real video files (`test1.mp4`, `test2.mp4`, `test3.mp4`), zero schema violations, reliable fire, smoke, and person detections.
- **Frontends**: Dual presentation available (Production-ready modern React app in `frontend/` and rapid diagnostic Streamlit app in `dashboard/`).
