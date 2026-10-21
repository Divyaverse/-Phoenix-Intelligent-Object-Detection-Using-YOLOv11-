# PHOENIX — Reviewer Data, Storage & Four-Role RBAC Guide

## 1. Project Overview & System Architecture

PHOENIX is an intelligent multi-layer fire and smoke perception, spatial hazard risk analysis, and evacuation decision-support system. It bridges real-time computer vision inference with spatial building topology to assist both emergency personnel and building occupants during hazardous events.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                             PHOENIX ARCHITECTURE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  [ FRONTEND - React 19 + TypeScript + Vite (Port 3000) ]                    │
│    ├── Top Header Bar (RBAC Session Switcher & Storage Explorer Navigation) │
│    ├── 3-Column Operations Hub:                                            │
│    │     ├── Left: CCTV Matrix (Staff) / Civilian Privacy Mode (Occupant)   │
│    │     ├── Center: Floorplan SVG with Live Hazard Decay & A* Egress Route │
│    │     └── Right: Role-Specific Tactical HUD (Occupant/Responder/Mgr/Admin│
│    └── Dedicated "Data & Storage Explorer" Modal/Console                    │
│                                                                             │
│                            │ HTTP (Bearer JWT)                              │
│                            ▼ WebSocket (/api/v1/ws/events)                  │
│                                                                             │
│  [ BACKEND - FastAPI + Python 3.14 + Uvicorn (Port 8000) ]                  │
│    ├── Core Security: Argon2id Hashing, Signed JWT (HS256), Refresh Tokens  │
│    ├── Auth & RBAC Dependencies: require_role([UserRole...])                 │
│    ├── Video Ingestion & Pipeline Service (video_service.py)                │
│    ├── Dual-Model YOLOv11 Perception (Ultralytics PyTorch)                  │
│    │     ├── Flame/Smoke Detection: models/fire_smoke_best.pt (5.46 MB)     │
│    │     └── Person Detection: models/yolo11n.pt (5.61 MB)                  │
│    ├── Temporal Smoke Analysis: Δarea/Δt plume growth tracking              │
│    ├── Spatial Mapping: 3x3 Planar Homography Perspective Projection        │
│    ├── Deterministic Risk Assessment: Node-level exponential hazard decay   │
│    └── Evacuation Routing: NetworkX Dijkstra / A* multi-factor graph engine │
│                                                                             │
│                            │ Parameterized SQL                              │
│                            ▼ (WAL Mode, Foreign Keys)                       │
│                                                                             │
│  [ PERSISTENT STORAGE - Local Managed Filesystem & SQLite ]                 │
│    ├── Database: C:\Phoniex\phoenix.db (36.2 MB, 17 relational tables)      │
│    ├── Uploaded Videos: C:\Phoniex\storage\videos\<video_id>\source.mp4     │
│    ├── Job Artifacts: C:\Phoniex\storage\jobs\<job_id>\annotated_<id>.mp4   │
│    └── Model Checkpoints: C:\Phoniex\models\*.pt                            │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Four-Role RBAC Permission Matrix

PHOENIX enforces strict Role-Based Access Control on every API endpoint and interface capability. Permissions are never determined by client-side state; every request is cryptographically validated on the server.

| Capability / Resource | SUPERADMIN | BUILDING_MANAGER | FIRST_RESPONDER | OCCUPANT |
| :--- | :---: | :---: | :---: | :---: |
| **System Health & Public Config** (`/system/health`) | ✅ Full | ✅ Full | ✅ Full | ✅ Full |
| **Active Incidents & Hazards** (`/incidents/current`) | ✅ Full | ✅ Full | ✅ Full | ✅ Read-Only Alerts |
| **Dynamic Evacuation Routing** (`/routes/current`) | ✅ Full | ✅ Full | ✅ Tactical | ✅ Civilian Egress |
| **CCTV Camera Surveillance Matrix** (`/cameras`) | ✅ Full | ✅ Building-Scoped | ✅ Incident Feeds | ❌ **Forbidden (403)** |
| **Video Ingestion & YOLO Inference** (`/videos/upload`) | ✅ Full | ✅ Authorized | ✅ Incident Footage | ❌ **Forbidden (403)** |
| **User & Account Directory** (`/auth/users`, `/explorer/users`) | ✅ Full | ✅ Building-Scoped | ❌ **Forbidden (403)** | ❌ **Forbidden (403)** |
| **Storage & Database Explorer** (`/explorer/*`) | ✅ Full | ✅ Operational View| ❌ **Forbidden (403)** | ❌ **Forbidden (403)** |
| **Reviewer Audit JSON/CSV Export** (`/explorer/export`) | ✅ Full | ✅ Authorized | ❌ **Forbidden (403)** | ❌ **Forbidden (403)** |

### Clarification on OCCUPANT Camera Access
In accordance with life-safety privacy standards, **Occupants are strictly barred from direct CCTV camera feeds**. When logged in as an Occupant, PHOENIX enters **Civilian Life-Safety & Privacy Mode**, which silences surveillance matrix network requests and directs the user to real-time evacuation waypoints, exit routes, and assembly check-in.

---

## 3. Authentication & Authorization Lifecycle

```
[ Client Login Request ] ─── POST /api/v1/auth/login ───► [ Argon2id Password Check ]
                                                                      │ Valid
                                                                      ▼
[ Token Response ] ◄── JWT Signed with HS256 Secret ◄─── [ Session Created in DB ]
  ├── access_token (15m expiry)                            (Table: auth_sessions)
  ├── user_id
  ├── role
  └── organization_id
        │
        ├── Stored in Browser localStorage (phoenix_token, phoenix_user_id, etc.)
        │
        ▼ Subsequent API Requests
[ Request Header ] ─── Authorization: Bearer <access_token> ───► [ FastAPI Depends ]
                                                                      │
                                                ┌─────────────────────┴──────────────────────┐
                                                ▼                                            ▼
                                        [ get_current_user ]                         [ require_role ]
                                    - Decodes JWT Signature                     - Checks decoded role
                                    - Validates expiration                      - Rejects unauthorized (403)
                                    - Queries users table in DB                 - Injects payload into router
```

### Root Cause of the Confirmed Symptom (OCCUPANT / SUPERADMIN Mismatch)
- **Symptom:** The browser received `HTTP 403: {"detail": "User role 'OCCUPANT' is not authorized for this resource"}` on `GET /api/v1/cameras?building_id=bldg-hq-01`, while the dashboard header displayed `usr-admin-01 (SUPERADMIN)`.
- **Root Cause:** In the previous implementation, the role selector buttons in the UI header called `switchRole(r)`, which only updated React local state and browser `localStorage` (`phoenix_role`, `phoenix_user_id`). It **never logged into the backend or exchanged the JWT access token**. Consequently, the browser continued sending the original Occupant JWT token (`usr-occ-01`). The backend properly derived identity and permissions from the cryptographically verified JWT bearer token and rejected the camera list with `HTTP 403 Forbidden`. The frontend, however, displayed unverified local state in the header.
- **Targeted Fix:** 
  1. `AuthContext.tsx` was upgraded with `switchAccount(targetRole)`. Clicking a role view now initiates an authentic backend login using that role's seed credentials, updates `phoenix_token` with a genuine signed JWT, and verifies the active identity against `/api/v1/auth/me`.
  2. The dashboard header was bound directly to `{userProfile?.user_id} ({userProfile?.role})` derived from the verified backend session profile.
  3. `DashboardPage.tsx` was updated with role-aware data loading: if `role === 'OCCUPANT'`, it suppresses CCTV camera calls and displays the civilian privacy notice, completely preventing false 403 errors.

---

## 4. Stored Identifiers and Credential Security

- **User Accounts:** Stored in the `users` table of `phoenix.db`.
  - Primary Key: `user_id` (e.g., `usr-admin-01`, `usr-mgr-01`, `usr-resp-01`, `usr-occ-01`).
  - Passwords: Protected using modern **Argon2id** (`$argon2id$v=19$m=65536,t=3,p=4$...`). Passwords are never stored in plaintext.
- **Active Sessions:** Tracked in the `auth_sessions` table with cryptographic session UUIDs, client user-agents, IP addresses, and revocation timestamps.
- **Access Tokens:** Signed JSON Web Tokens containing `sub` (User ID), `role`, `org_id`, `exp`, and `jti`. Stored client-side in memory and synchronized to `localStorage` under `phoenix_token`.
- **Protection of Secrets:** Neither the Data & Storage Explorer nor the Reviewer Export Report ever displays or exports password hashes, secret signing keys, or token signatures.

---

## 5. Actual Database Path, Engine & Schema

- **Configured Path:** `C:\Phoniex\phoenix.db`
- **Database Engine:** SQLite 3.x
- **Journal Mode:** Write-Ahead Logging (`WAL` mode enabled for concurrent read-write transactions)
- **Foreign Key Constraints:** Enforced (`PRAGMA foreign_keys = ON;`)
- **Total Record Count:** **96,476+ records** across **17 relational tables**

### Relational Table Directory

| Table Name | Primary Key | Description & Foreign Keys |
| :--- | :--- | :--- |
| `users` | `user_id` | Operator accounts, Argon2id password hashes, roles, and status |
| `auth_sessions` | `session_id` | Revocable active and historical refresh token sessions (`FK -> users.user_id`) |
| `organizations` | `organization_id` | Multi-tenant organizational partition records |
| `buildings` | `building_id` | Facility structures, addresses, and physical metadata (`FK -> organizations`) |
| `floors` | `floor_id` | Floor dimensions, elevation, scale references (`FK -> buildings`) |
| `cameras` | `camera_id` | Monitored CCTV camera feeds, RTSP URIs, and status (`FK -> floors`) |
| `calibrations` | `calibration_id` | 3x3 planar homography transformation matrices (`FK -> cameras`) |
| `floorplans` | `floorplan_id` | Architectural floorplan polygons, exits, and graphs (`FK -> floors`) |
| `video_sources` | `video_id` | Ingested source video files, SHA-256 checksums, and paths |
| `processing_jobs` | `job_id` | Background YOLO perception jobs and status (`FK -> video_sources`) |
| `video_frames` | `frame_id` | Decoded frame samples, timestamps, and keyframe paths (`FK -> processing_jobs`) |
| `detections` | `detection_id` | YOLOv11 bounding boxes, classes, and confidences (`FK -> video_frames`) |
| `temporal_analyses` | `analysis_id` | 2D smoke plume surface areas (px²) and growth rates (`FK -> processing_jobs`) |
| `risk_events` | `snapshot_id` | Spatial hazard levels and per-node risk scores (`FK -> processing_jobs`) |
| `incidents` | `incident_id` | Confirmed active and resolved emergency incidents (`FK -> buildings`) |
| `route_recommendations` | `route_id` | Multi-factor Dijkstra evacuation routes and ETAs (`FK -> incidents`) |
| `audit_events` | `audit_id` | Tamper-evident append-only system audit log |

---

## 6. Physical Storage Layout

All persistent artifacts are stored within the managed project workspace:

- **Primary Database:** `C:\Phoniex\phoenix.db` (36.2 MB)
- **Uploaded Source Videos:** `C:\Phoniex\storage\videos\<video_id>\source.mp4`
- **Perception Output Videos:** `C:\Phoniex\storage\jobs\<job_id>\annotated_<video_id>.mp4`
- **Keyframe Bounding Boxes:** `C:\Phoniex\storage\jobs\<job_id>\keyframes\frame_*.jpg`
- **Default CCTV Demonstration Videos:** `C:\Phoniex\videos\Main_video.mp4` (and secondary CCTV feeds `test1.mp4`, `test2.mp4`, `test3.mp4`)
- **YOLOv11 PyTorch Model Weights:**
  - Fire & Smoke Perception: `C:\Phoniex\models\fire_smoke_best.pt` (5.46 MB)
  - Person Detection & Headcount: `C:\Phoniex\models\yolo11n.pt` (5.61 MB)

---

## 7. How to Access and Demonstrate the Data & Storage Explorer

1. Open your browser and navigate to the application: `http://localhost:3000/`.
2. In the top header bar, click the **`⚡ SuperAdmin`** role button.
   - The user indicator in the header will update to: **`usr-admin-01 (SUPERADMIN)`**.
3. In the top header bar, click the purple **`🗄️ Data & Storage Explorer`** button.
4. The application transitions to the Reviewer Explorer with 5 comprehensive inspection views:
   - **Tab 1 (Storage & Checkpoints):** View verified paths, existence checks, file sizes, and timestamps for the SQLite database, uploaded video repository, job artifacts, and YOLO model checkpoints.
   - **Tab 2 (User Accounts & Identity):** Inspect all 4 registered user accounts with roles, organization IDs, and status. Review the clear architectural breakdown differentiating User IDs, Roles, and Access Tokens. Notice that no passwords or token signatures are displayed.
   - **Tab 3 (Database Tables & Records):** Explore all 17 SQLite tables, primary keys, and real-time row counts totaling over 96,000 records.
   - **Tab 4 (Video & Perception Jobs):** View the paginated history of background perception jobs. Click any job row to view sample detection records, bounding boxes, temporal smoke telemetry, and annotated video status.
   - **Tab 5 (Data Lineage Flow):** Review the end-to-end data processing lineage. Click the **"📥 Export Reviewer Audit Report (JSON)"** button to generate a sanitized audit document.
5. Click **`📊 Live Operations Dashboard`** in the header to return to the real-time operations console.

---

## 8. Tracing a Video ID to Processing Results

When a video is uploaded or inspected:
1. In the **Video & Perception Jobs** tab of the Explorer, locate the `video_id` or `job_id`.
2. Inspect the associated metadata:
   - File storage location: `storage/videos/<video_id>/source.mp4`
   - Processing status: `COMPLETED`
   - Frame count, detection count, and runtime duration
   - Annotated output video: `storage/jobs/<job_id>/annotated_<video_id>.mp4`
3. Click on the job row: the inspector loads real bounding boxes from the `detections` table and temporal smoke records from the `temporal_analyses` table.

---

## 9. Genuine Processing vs. Simulated Dashboard Values

To ensure absolute academic and technical honesty during evaluation, PHOENIX clearly delineates genuine processing from illustrative facility values:

### Genuine Implementations (Active Code & Real Models)
- **YOLOv11 Inference:** Ran by Ultralytics PyTorch using `fire_smoke_best.pt` and `yolo11n.pt`. Bounding boxes and confidences come directly from model tensors.
- **Temporal Smoke Growth:** Derived from frame-by-frame 2D pixel area expansion ($\Delta \text{area} / \Delta t$) smoothed via Exponential Moving Average (EMA).
- **Planar Homography Calibration:** 3x3 perspective transformation matrix mapping image pixel coordinates $(u, v)$ to metric floorplan coordinates $(X, Y)$.
- **Spatial Risk Engine:** Deterministic spatial risk decaying exponentially ($e^{-\lambda d}$) across floorplan navigation nodes based on hazard coordinates.
- **Shortest Evacuation Path:** Dijkstra / A* graph computation implemented via NetworkX using actual floorplan edge distances, hazard exposure factors, and blockage penalties.
- **Persistence & RBAC:** SQLite ACID transactions across 17 tables, Argon2id password hashing, and role-based route dependencies.

### Simulated / Emulated Telemetry (Explicitly Tagged in UI)
- **Building Zone Headcount:** Labeled as `[SIMULATED BADGE TELEMETRY]`. Instantaneous person detections per frame do not represent unique building headcount (which requires persistent multi-camera re-identification tracking).
- **Life-Safety Hardware State (HVAC & Fire Doors):** Labeled as `[BUILDING AUTOMATION EMULATION]`. Indicates what commands would be dispatched to a BACnet or Modbus building management system.
- **Standby Benchmarks:** Standby microservice metrics (12ms latency, 31.2 FPS) represent benchmark baseline performance on the host hardware. When an uploaded video is processed, the actual calculated FPS is displayed dynamically.

---

## 10. Verification & Test Execution Results

All automated tests passed successfully with 0 failures:

```bash
# 1. Four-Role RBAC and Data & Storage Explorer Integration Tests
python -m pytest tests/integration/test_four_role_rbac_explorer.py -v
============================= 16 passed in 15.44s =============================

# 2. Database Persistence, Security, and Upload E2E Tests
python -m pytest tests/integration/test_persistence_security_e2e.py -v
============================= 12 passed in 19.83s =============================

# 3. Frontend TypeScript & Production Build Verification
npm run build (in frontend/)
vite v8.3.1 building client environment for production...
✓ 26 modules transformed.
dist/index.html                   0.45 kB │ gzip:  0.29 kB
dist/assets/index-Dj6BWiVv.css    0.30 kB │ gzip:  0.24 kB
dist/assets/index-D1pg-_II.js   339.41 kB │ gzip: 95.37 kB
✓ built in 1.51s
```
