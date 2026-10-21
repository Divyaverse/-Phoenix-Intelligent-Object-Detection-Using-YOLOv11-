# PHOENIX — Bug Fix Summary & Implementation Log

This document provides a concise record of all bugs identified, root causes, files modified, and verification results.

---

## 1. Primary Bug: OCCUPANT / SUPERADMIN Identity & Permission Mismatch

### Symptom
- Browser console displayed: `HTTP 403 {"detail": "User role 'OCCUPANT' is not authorized for this resource"}` on `GET /api/v1/cameras?building_id=bldg-hq-01`.
- The dashboard top header bar appeared to display: `usr-admin-01 (SUPERADMIN)`.

### Root Cause
1. In `DashboardPage.tsx`, clicking the role switcher buttons called `switchRole(newRole)` from `AuthContext.tsx`.
2. `switchRole` only mutated local React state and `localStorage` values (`phoenix_role`, `phoenix_user_id`), but **never called the backend login endpoint or refreshed the JWT bearer token**.
3. The stored access token in `phoenix_token` remained the token issued to `usr-occ-01` (OCCUPANT).
4. When `ApiClient.getCameras('bldg-hq-01')` was executed, the HTTP request sent `Authorization: Bearer <occupant_token>`.
5. The backend endpoint dependency `require_role([UserRole.SUPERADMIN, UserRole.BUILDING_MANAGER, UserRole.FIRST_RESPONDER])` verified the token cryptographically and correctly rejected the request with `403 Forbidden`.
6. `DashboardPage.tsx` initial data loader caught the error and silently rendered mock camera objects, masking the actual failure state.

### Targeted Fix Applied
1. **`frontend/src/context/AuthContext.tsx`**:
   - Replaced client-only role mutation with `switchAccount(targetRole)`.
   - Mapped seed credentials for all four roles (`admin@phoenix.local`, `manager@phoenix.local`, `responder@phoenix.local`, `occupant@phoenix.local`).
   - Switching roles now executes a genuine authentication call to `/api/v1/auth/login`, stores the newly issued verified JWT, and loads the user profile via `/api/v1/auth/me`.
2. **`frontend/src/components/DashboardPage.tsx`**:
   - Bound top header user identity directly to `{userProfile?.user_id || userId} ({userProfile?.role || role})`.
   - Wired `handleRoleSwitch(r)` to `switchAccount(r)` with visual feedback.
   - Made camera loading role-aware: if `role === 'OCCUPANT'`, camera requests are withheld, and a dedicated **Civilian Life-Safety & Privacy Mode** card is rendered.
   - If camera requests fail for authorized staff, the actual error is rendered in the UI instead of silently falling back to mock objects.

---

## 2. Status Indicators & Misleading Placeholder Values

### Symptom
- Health and WebSocket indicator dots remained hardcoded green (`#22c55e`) regardless of actual connection state.
- Occupant safe exit name, directions, and ETA were hardcoded strings.
- Facility headcount and hardware states were presented without labeling source or simulation status.

### Targeted Fix Applied
- **Indicators:** Dot color dynamically driven by `health?.status` (green for `HEALTHY`, yellow for `DEGRADED`, red for `OFFLINE`) and `isConnected` (green for `LIVE`, red for `DISCONNECTED`).
- **Occupant HUD:** Exit name bound to dynamic `route?.destination_node` (e.g., Exit South vs Exit North); ETA bound to calculated `route?.eta_seconds`; step-by-step corridor waypoints derived dynamically from `route?.path_nodes`.
- **Honest Labeling:** Added clear UI tags distinguishing real perception calculations from simulated facility infrastructure:
  - Zone Headcount: tagged `[SIMULATED BADGE TELEMETRY]` with footnote explaining that raw person detections per frame do not represent unique building occupancy.
  - Life-Safety Hardware: tagged `[BUILDING AUTOMATION EMULATION]`.
  - Microservice Metrics: tagged `[REAL TELEMETRY & BENCHMARKS]` with dynamic calculated FPS for uploaded videos.

---

## 3. Dedicated Data & Storage Explorer

### Architecture Added
- **Backend (`app/api/routes/explorer.py`)**:
  - `GET /api/v1/explorer/overview`: Inspects `phoenix.db`, filesystem directories (`storage/videos`, `storage/jobs`, `models`), and model checkpoint files (`fire_smoke_best.pt`, `yolo11n.pt`).
  - `GET /api/v1/explorer/users`: Safe user directory showing User ID, email, role, and creation timestamp. Completely excludes passwords, password hashes, and tokens.
  - `GET /api/v1/explorer/database`: Inspects all 17 SQLite tables, primary keys, and live row counts (96,476+ records).
  - `GET /api/v1/explorer/jobs`: Paginated processing jobs showing frames processed, detection counts, execution duration, and annotated video status.
  - `GET /api/v1/explorer/jobs/{job_id}/sample`: Safe read-only inspection of bounding box detections and temporal smoke analysis records. Includes path traversal protection.
  - `GET /api/v1/explorer/export`: Reviewer audit export in sanitized JSON format.
  - Enforces `require_role([SUPERADMIN, BUILDING_MANAGER, FIRST_RESPONDER])` — returns 403 Forbidden for OCCUPANT.
- **Frontend (`frontend/src/components/DataStorageExplorer.tsx`)**:
  - 5 interactive tabs: Storage & Checkpoints, User Accounts & Identity, Database Tables & Records, Video & Perception Jobs, and Data Lineage Flow.
  - Includes interactive sample viewer for job detection records and one-click JSON export.

---

## 4. Summary of Created & Modified Files

| File | Status | Description |
| :--- | :--- | :--- |
| `app/api/routes/explorer.py` | **Created** | Read-only reviewer storage, database, and job inspection endpoints with RBAC. |
| `app/main.py` | **Modified** | Mounted `explorer_router` under `/api/v1`. |
| `frontend/src/types/phoenix.ts` | **Modified** | Added TypeScript interfaces for storage overview, database, and job explorer responses. |
| `frontend/src/services/apiClient.ts` | **Modified** | Added client methods for explorer endpoints and current user profile. |
| `frontend/src/context/AuthContext.tsx` | **Modified** | Implemented authentic account switching, profile validation, and session synchronization. |
| `frontend/src/components/DataStorageExplorer.tsx` | **Created** | Comprehensive Reviewer Data & Storage Explorer component with 5 tabs. |
| `frontend/src/components/DashboardPage.tsx` | **Modified** | Linked Explorer, role-aware camera fetching, civilian privacy mode, dynamic route HUD, and honest labeling. |
| `tests/integration/test_four_role_rbac_explorer.py` | **Created** | 16 automated tests covering all 4 roles, camera RBAC, explorer endpoints, and path traversal safety. |
| `docs/reviewer_data_storage_guide.md` | **Created** | Comprehensive reviewer documentation detailing architecture, storage, and demonstration steps. |
| `docs/bug_fix_summary.md` | **Created** | Concise bug-fix summary and implementation log. |
| `backups/*` | **Created** | Timestamped backups created prior to modifying any existing files. |

---

## 5. Verification Summary
- **RBAC & Explorer Tests:** `16 passed in 15.44s`
- **Persistence & Security Tests:** `12 passed in 19.83s`
- **Total Tests Passing:** **28 / 28 passed** (0 failures, 0 errors)
- **Frontend Production Build:** `tsc -b && vite build` completed in 1.51s with 0 errors.
- **Database Integrity:** Existing SQLite database `C:\Phoniex\phoenix.db` remained 100% intact with zero deleted records or reset tables.
