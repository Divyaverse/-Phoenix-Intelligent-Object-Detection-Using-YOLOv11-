# PHOENIX Testing Strategy

## Test Pyramid & Categories

```
           / \
          /   \
         / E2E \         (End-to-end pipeline & Streamlit UI flow)
        /-------\
       / Failure \       (Model dropout, DB lock, camera disconnect, no route)
      /-----------\
     / Integration \     (Perception -> Spatial -> Decision -> Routing -> Event)
    /---------------\
   /   Unit Tests    \   (Pure logic: models, temporal growth, homography, cost)
  /-------------------\
```

### 1. Unit Tests (`tests/unit/`)
- Domain models and enums validation
- Temporal growth rate formula calculations
- Homography coordinate transformation accuracy
- Deterministic risk engine scoring
- NetworkX graph construction and edge cost calculations
- ETA estimation with various penalty combinations

### 2. Integration Tests (`tests/integration/`)
- FrameSource &rarr; YOLO Adapter &rarr; Structured Detections
- Detections &rarr; Homography &rarr; Risk Snapshot &rarr; Route Calculation
- Repositories &rarr; SQLite transactional commits and rollbacks

### 3. Contract Tests (`tests/contract/`)
- FastAPI REST request and response schema validation
- WebSocket event envelope validation and sequence monotonicity

### 4. Security Tests (`tests/security/`)
- JWT token verification (valid, expired, malformed)
- Role-based access control enforcement (SuperAdmin, BuildingManager, FirstResponder, Occupant)
- Cross-tenant data isolation

### 5. Failure Injection Tests (`tests/failure/`)
- Unavailable YOLO model checkpoint &rarr; explicit `AI_DEGRADED` status
- Disconnected camera feed &rarr; explicit `CAMERA_OFFLINE`
- Degraded/insufficient calibration points &rarr; explicit `SPATIAL_MAPPING_UNAVAILABLE`
- Fully blocked exit routes &rarr; explicit `NO_VALID_ROUTE` / `NO_VALID_EXIT` (never invented routes)
- SQLite database lock/unavailability &rarr; explicit `PERSISTENCE_UNAVAILABLE`

### 6. Running Tests
```bash
pytest -v --cov=app --cov-report=term-missing
```
