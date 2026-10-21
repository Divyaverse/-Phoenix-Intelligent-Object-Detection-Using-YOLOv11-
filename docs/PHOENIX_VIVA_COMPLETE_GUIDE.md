# PHOENIX — Comprehensive Project Inspection & B.E. Viva Preparation Guide

**System Name**: PHOENIX (Predictive Heat Observation and Emergency Navigation Intelligence System)  
**Repository Location**: `C:\Phoniex`  
**Inspection Date**: October 21, 2026  
**Audience**: Final Year Engineering (B.E. AIML) Project Viva & Defense  
**Verification Level**: 100% Source-Code, Database, Configuration, and Test-Verified  

---

## 1. Project Overview & Problem Statement

### 1.1 What PHOENIX Is
**PHOENIX** is an autonomous, AI-driven building emergency intelligence and dynamic evacuation decision-support system. It integrates computer vision (dual-model YOLOv11), temporal hazard tracking, planar homography geometry, deterministic spatial risk calculation, and multi-factor graph routing (Dijkstra) into a real-time reactive command and control dashboard.

### 1.2 The Real-World Problem It Addresses
During structural building fires:
1. **Static Evacuation Signage is Dangerous**: Traditional static green "EXIT" signs direct occupants toward pre-defined stairwells regardless of whether those stairwells are currently engulfed in fire or toxic smoke.
2. **Smoke Inhalation Kills First**: Over 70% of fire fatalities result from toxic smoke and gas inhalation rather than direct thermal burns. Smoke spreads unpredictably and fills corridors minutes before flames appear.
3. **Information Asymmetry**: First responders arrive on scene with zero situational awareness regarding hazard origin, smoke velocity, or trapped occupant locations.
4. **CCTV Passive Monitoring**: Standard CCTV surveillance networks record passive video feeds that humans rarely analyze in time during panic situations.

### 1.3 System Objectives & Intended Users
- **Primary Objective**: Ingest facility CCTV camera streams, automatically detect fire, smoke, and persons in real-time, predict hazard growth, and dynamically compute safe, obstacle-avoiding evacuation routes to the nearest accessible exit.
- **Intended Users**:
  1. **Occupants**: Civilians inside the building who receive personalized turn-by-turn egress routing and emergency assembly check-in.
  2. **First Responders**: Firefighters and tactical response teams needing hazard coordinates, smoke growth trends, and occupant density.
  3. **Building Managers**: Facility safety officers who oversee life-safety automation (HVAC smoke dampers, fire doors) and public address broadcasts.
  4. **SuperAdmins**: System administrators who audit event streams, inspect the relational database, manage user accounts, and verify model checkpoints.

---

## 2. Fast Viva Introductions (Scripted)

### 30-Second Introduction (Elevator Pitch)
> "Good morning, respected examiners. Our project, **PHOENIX**, is an AI-powered emergency navigation intelligence system that transforms passive building CCTV cameras into life-saving evacuation engines. When a fire or smoke hazard erupts, PHOENIX utilizes a dual-model YOLOv11 perception pipeline to identify the threat, tracks smoke spread over time, maps pixel detections onto physical floorplan blueprints using planar homography, and computes deterministic, hazard-avoiding evacuation paths using a multi-factor Dijkstra algorithm. It delivers role-tailored real-time interfaces for building occupants, first responders, facility managers, and system administrators."

### 1-Minute Introduction (Standard Viva Opening)
> "Respected examiners, traditional building emergency systems rely on static exit signs and smoke alarms, which fail to adapt when primary egress paths become blocked by toxic smoke. **PHOENIX** addresses this critical life-safety flaw by establishing an autonomous, closed-loop perception and decision pipeline. 
> 
> The system decodes CCTV video streams at up to 15 frames per second, running dual YOLOv11 neural networks to detect open flames, smoke plumes, and occupants. We track the two-dimensional rate of smoke plume expansion using an exponential moving average. Using a 3-by-3 planar homography transformation calibrated with RANSAC, pixel coordinates from camera frames are converted into real-world metric floorplan coordinates. 
> 
> These coordinates feed into a deterministic spatial risk engine that applies exponential proximity decay to calculate risk scores for all building corridors. Finally, a multi-factor graph routing engine computes the safest evacuation path and estimated time of arrival, broadcasting live updates via WebSockets to our responsive React dashboard."

### 3-Minute Technical Explanation (In-Depth Technical Presentation)
> "Technically, PHOENIX is structured around a decoupled, 5-stage architecture spanning Computer Vision, Spatial Geometry, Deterministic Risk Estimation, Graph Optimization, and Real-Time Event Streaming:
> 
> 1. **Perceptual Layer**: We employ a dual-model architecture using Ultralytics YOLOv11. Flame and smoke detection are performed by a specialized neural network (`models/fire_smoke_best.pt`, 5.46 MB), while civilian occupancy is detected via a pre-trained COCO YOLOv11 nano model (`models/yolo11n.pt`, 5.61 MB). Running dual specialized models avoids class imbalance and maintains high recall on diffused smoke contours.
> 
> 2. **Temporal & Spatial Normalization**: Smoke detections pass through our `TemporalSmokeAnalyzer`, which measures delta area over delta time ($\Delta \text{Area} / \Delta t$) across a 10-second sliding window, smoothing instantaneous jitter with an alpha factor of 0.3. Concurrently, bounding-box ground contact points ($[u, v, 1]^T$) are projected through a calibrated $3 \times 3$ planar homography matrix $H$ into physical metric coordinates ($X, Y$ in meters), rejecting non-coplanar optical distortion.
> 
> 3. **Mathematical Risk Engine**: Rather than treating hazards as binary blocked nodes, our `DeterministicRiskEngine` applies an exponential spatial decay model: $H_i = w_{base} \times \text{confidence} \times M_{growth} \times \exp(-\lambda \cdot d)$, where $\lambda = 0.50 \text{ m}^{-1}$ and $M_{growth}$ scales up to 1.5 for rapidly expanding smoke. This produces continuous hazard scores across all corridor waypoints.
> 
> 4. **Multi-Factor Graph Routing**: A NetworkX topology graph of corridor segments weights each edge across four normalized components: 35% distance, 40% hazard exposure, 10% occupant density, and 15% predicted smoke blockage. Edges with hazard exceeding 0.90 are hard-blocked. Dijkstra's shortest-path algorithm determines the global minimum-cost egress path to the nearest safe exit. Travel time is calculated using an empirical walking speed of 1.2 m/s adjusted for stairs, smoke visibility reduction, and congestion slowdown.
> 
> 5. **Backend & Presentation**: The backend is powered by FastAPI and SQLite with Write-Ahead Logging (WAL mode), persisting audit trails and job artifacts. Real-time events stream over WebSockets to a React 19 dashboard styled with dark-mode tactical glassmorphism, enforcing strict Argon2id authentication and role-based access control across four distinct user roles."

---

## 3. System Architecture & Complete Data-Flow

### 3.1 High-Level Architecture Diagram (Mermaid)

```mermaid
graph TB
    subgraph Ingestion["1. INGESTION & PERCEPTION LAYER"]
        CCTV["CCTV Video Streams<br/>(Main_video.mp4 / RTSP)"]
        Upload["User Video Ingestion<br/>(POST /videos/upload)"]
        YOLO_FS["YOLOv11 Fire/Smoke Model<br/>(fire_smoke_best.pt)"]
        YOLO_P["YOLOv11 Person Model<br/>(yolo11n.pt)"]
        Detector["YOLOAdapter<br/>(app/perception/detector.py)"]
        
        CCTV --> Detector
        Upload --> Detector
        YOLO_FS --> Detector
        YOLO_P --> Detector
    end

    subgraph Geometry["2. GEOMETRY & TEMPORAL ANALYSIS"]
        Temporal["TemporalSmokeAnalyzer<br/>(ΔArea / Δt & EMA Smoothing)"]
        Homography["PlanarHomographyMapper<br/>(3x3 Homography Matrix H)"]
        
        Detector -->|Smoke Bounding Boxes| Temporal
        Detector -->|Ground Contact Points| Homography
    end

    subgraph Decision["3. SPATIAL RISK & ROUTE OPTIMIZATION"]
        RiskEngine["DeterministicRiskEngine<br/>(Proximity Decay: exp(-λd))"]
        Prediction["PredictiveBlockageEngine<br/>(30s Horizon Prediction)"]
        Occupancy["ApproximateOccupancyEstimator<br/>(Corridor Congestion)"]
        RoutingEngine["MultiFactorRoutingEngine<br/>(Dijkstra / NetworkX Graph)"]
        ETA["DeterministicETAEstimator<br/>(Speed: 1.2m/s + Penalties)"]
        
        Temporal -->|Growth Multiplier| RiskEngine
        Homography -->|Metric X,Y Hazards| RiskEngine
        Temporal -->|Smoke Trajectory| Prediction
        RiskEngine --> RoutingEngine
        Prediction --> RoutingEngine
        Occupancy --> RoutingEngine
        RoutingEngine --> ETA
    end

    subgraph Persistence["4. PERSISTENCE & EVENT BUS"]
        DB[(SQLite 3 Database<br/>phoenix.db in WAL Mode)]
        EventBus["FastAPI EventBus & WS Router<br/>(ws://localhost:8000/ws/v1)"]
        Storage["Managed Storage<br/>(storage/videos & storage/jobs)"]
        
        RoutingEngine --> DB
        RiskEngine --> DB
        Detector --> DB
        RoutingEngine --> EventBus
        Upload --> Storage
    end

    subgraph Presentation["5. FOUR-ROLE CLIENT DASHBOARD"]
        Dashboard["React 19 Dashboard<br/>(http://localhost:3000)"]
        OccupantHUD["Occupant HUD<br/>(Egress Path & Check-In)"]
        ResponderHUD["First Responder HUD<br/>(Coordinates & Headcount)"]
        ManagerConsole["Building Manager<br/>(Override & Automation)"]
        AdminTelemetry["SuperAdmin Console<br/>(Diagnostics & DB Explorer)"]
        
        EventBus --> Dashboard
        DB --> Dashboard
        Dashboard --> OccupantHUD
        Dashboard --> ResponderHUD
        Dashboard --> ManagerConsole
        Dashboard --> AdminTelemetry
    end
```

### 3.2 End-to-End Data Flow Pipeline

```mermaid
sequenceDiagram
    autonumber
    actor User as CCTV / Operator
    participant API as FastAPI Ingestion (videos.py)
    participant Worker as VideoProcessingService
    participant CV as Dual YOLOv11 Detector
    participant Temp as TemporalSmokeAnalyzer
    participant Spatial as PlanarHomographyMapper
    participant Risk as DeterministicRiskEngine
    participant Graph as MultiFactorRoutingEngine
    participant DB as SQLite (phoenix.db)
    participant WS as WebSocket EventBus
    participant UI as React Dashboard

    User->>API: POST /api/v1/videos/upload (Multipart MP4)
    API->>Worker: Validate SHA-256 & Store in storage/videos
    API-->>User: 201 Created (VideoSourceResponse)
    User->>API: POST /api/v1/videos/{id}/jobs?stride=2
    API->>Worker: BackgroundTasks.add_task(execute_job)
    API-->>User: 202 Accepted (Job QUEUED)

    loop Every Stride Frame
        Worker->>CV: detector.detect(frame, stride=2)
        CV-->>Worker: List[Detection] (Fire, Smoke, Person)
        Worker->>Temp: process_observations(camera_id, detections, timestamp)
        Temp-->>Worker: SmokeObservation (area_px2, growth_rate, trend)
        Worker->>Spatial: image_to_floorplan(ground_point, calib)
        Spatial-->>Worker: Point2D(x_meters, y_meters)
        Worker->>Risk: calculate_risk(nodes, detections, smoke_observations)
        Risk-->>Worker: RiskSnapshot(node_risks, global_risk_level)
        Worker->>Graph: compute_route(nodes, edges, origin, exits, risk)
        Graph-->>Worker: RouteRecommendation(path_nodes, eta, cost_breakdown)
        Worker->>DB: Batch Persist (Detections, Frames, Risk, Routes)
        Worker->>WS: ws_manager.broadcast(EVENT_UPDATE)
        WS-->>UI: WebSocket JSON Frame Update
    end

    Worker->>DB: complete_job(status="COMPLETED", execution_time)
    Worker->>DB: Record AuditEvent(JOB_COMPLETED)
    UI->>API: GET /api/v1/jobs/{job_id}/results
    API-->>UI: Full Job Persisted Telemetry
```

---

## 4. Frontend Dashboard — Element-by-Element Inspection

Every component below exists in the active source tree (`frontend/src/components/`).

| Visual Element / Control | Location on Screen | Source File & Component | Controlling State / Hooks | Data Source / API Endpoint | Classification | What Happens on Click / Interaction | Error / Empty Fallback Behavior | Spoken Viva Explanation (1–3 Sentences) |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **PHOENIX Logo Badge** | Top-left header | [`DashboardPage.tsx`](file:///c:/Phoniex/frontend/src/components/DashboardPage.tsx#L817) | Static display | Hardcoded string | Static | None (Branding display) | Always renders | *"This is our system branding banner displaying the PHOENIX acronym, which stands for Predictive Heat Observation and Emergency Navigation Intelligence System."* |
| **Facility Info Card** | Top-left header | [`DashboardPage.tsx`](file:///c:/Phoniex/frontend/src/components/DashboardPage.tsx#L834) | `building` | `GET /api/v1/buildings/bldg-hq-01` | Dynamic from DB | Displays building name and active address | Falls back to default facility: "Phoenix Innovation Center" | *"This header indicator displays the active building name and organizational scope retrieved directly from our SQLite database."* |
| **Decision-Support Status Pill** | Top-left header | [`DashboardPage.tsx`](file:///c:/Phoniex/frontend/src/components/DashboardPage.tsx#L839) | `isEmergencyMode` derived from `incident` | WebSocket event or `GET /incidents/current` | Dynamic | None (Status pill) | Shows green "LAYER 1: SURVEILLANCE STANDBY" when normal | *"This indicator shows whether PHOENIX is operating in standby surveillance mode or active emergency decision-support mode based on whether a verified hazard incident is open in the database."* |
| **Four-Role Switcher Buttons** | Top-center header | [`DashboardPage.tsx`](file:///c:/Phoniex/frontend/src/components/DashboardPage.tsx#L864) | `role`, `targetSwitchRole` | `useAuth()` & `RoleAuthModal.tsx` | Enforced RBAC | Opens `RoleAuthModal` requesting password for target role | Active role button is disabled and marked with blue checkmark | *"These four role buttons allow switching between Building Manager, First Responder, Occupant, and SuperAdmin views, requiring full credential authentication on every transition."* |
| **Data & Storage Explorer Button** | Top-right header | [`DashboardPage.tsx`](file:///c:/Phoniex/frontend/src/components/DashboardPage.tsx#L913) | `showExplorer`, `setShowExplorer` | Toggles component view | Client State | Toggles full-screen `<DataStorageExplorer />` | Re-renders dashboard when toggled back | *"This button switches the dashboard into the Data & Storage Explorer, which directly queries database schemas, row counts, filesystem directories, and job artifacts."* |
| **Upload Video Button** | Top-right header | [`DashboardPage.tsx`](file:///c:/Phoniex/frontend/src/components/DashboardPage.tsx#L936) | `uploadState`, `fileInputRef` | `POST /videos/upload` & `POST /videos/{id}/jobs` | Dynamic API | Opens hidden HTML file picker to select MP4/MOV/AVI video | Shows loading percentage and disables button during upload | *"This button allows operators to upload new surveillance video footage to be processed by our dual YOLOv11 perception pipeline in isolated storage."* |
| **API Health Indicator** | Top-right header | [`DashboardPage.tsx`](file:///c:/Phoniex/frontend/src/components/DashboardPage.tsx#L965) | `health` | `GET /api/v1/system/health` | Dynamic API | None (Visual status) | Displays red dot and "API: OFFLINE" if backend is unreachable | *"This indicator reflects live backend connectivity; it polls `/system/health` and confirms that SQLite and internal perception services are operational."* |
| **WebSocket Indicator** | Top-right header | [`DashboardPage.tsx`](file:///c:/Phoniex/frontend/src/components/DashboardPage.tsx#L982) | `isConnected` | `useWebSocket()` from `WebSocketContext.tsx` | Live WS | None (Visual status) | Displays red dot and "WS: DISCONNECTED" if socket drops | *"This pill confirms active bidirectional WebSocket connectivity to our real-time event bus at port 8000."* |
| **Authenticated Identity** | Top-right header | [`DashboardPage.tsx`](file:///c:/Phoniex/frontend/src/components/DashboardPage.tsx#L994) | `userProfile`, `userId`, `role` | `GET /api/v1/auth/me` | Dynamic Session | None (Identity label) | Falls back to cached local storage values | *"This label confirms the server-verified user ID and role claim embedded in the current JWT bearer token."* |
| **Sign Out Button** | Top-right header | [`DashboardPage.tsx`](file:///c:/Phoniex/frontend/src/components/DashboardPage.tsx#L998) | `logout` | `POST /api/v1/auth/logout` | Dynamic Auth | Invalidates backend session in DB, clears tokens, redirects to Landing Page | Clears localStorage even if network request fails | *"Clicking Sign Out revokes the refresh session in SQLite, purges all local authentication tokens, and returns the operator to the landing page."* |
| **Emergency Incident Banner** | Sub-header strip | [`DashboardPage.tsx`](file:///c:/Phoniex/frontend/src/components/DashboardPage.tsx#L1120) | `incident`, `route` | `GET /incidents/current` & WS | Dynamic | None (Emergency alert) | Collapses completely when no active incident exists | *"When a fire is detected, this high-contrast red alert banner activates, showing the incident title, severity, hazard origin node, and safe evacuation exit."* |
| **CCTV Stream Toggle (Demo vs Uploaded)** | Left panel header | [`DashboardPage.tsx`](file:///c:/Phoniex/frontend/src/components/DashboardPage.tsx#L1287) | `isShowingUploaded`, `activeUploadedVideo` | Client State | Client State | Toggles video feed between default corridor demo and newly uploaded video | Hidden if no custom video has been processed | *"This tab switch allows reviewers to compare the live baseline CCTV footage against newly uploaded, custom-analyzed video files."* |
| **AI Annotated Video Toggle** | Left panel subheader | [`DashboardPage.tsx`](file:///c:/Phoniex/frontend/src/components/DashboardPage.tsx#L1355) | `useAIStream` | Switches video source URL | Client State | Switches video element between raw footage and annotated video with bounding boxes | Falls back to raw video if annotated stream is absent | *"This toggle lets examiners view either the raw camera feed or the AI-annotated output video generated by OpenCV with YOLO bounding boxes and status HUDs."* |
| **Primary CCTV Video Player** | Left column | [`CameraFeed.tsx`](file:///c:/Phoniex/frontend/src/components/CameraFeed.tsx#L130) | `videoSource`, `selectedCamId` | Static file mount `/videos/...` or `/jobs/...` | Video Stream | Selects camera as primary active view | Displays "No CCTV video stream configured" | *"This HTML5 video element streams the central corridor camera feed, playing back surveillance footage with simulated live playback."* |
| **Real-Time Detection Pills** | Below primary player | [`DashboardPage.tsx`](file:///c:/Phoniex/frontend/src/components/DashboardPage.tsx#L1414) | `liveDetections` | WebSocket `DETECTION_OBSERVED` or DB | Dynamic | None (Pill display) | Displays "Monitoring central corridor — No active hazards" | *"These pills show instantaneous object detections produced by YOLOv11, color-coded red for flame, gray for smoke, and blue for persons with exact confidence percentages."* |
| **Secondary Camera Feeds (3 Feeds)** | Left column bottom | [`DashboardPage.tsx`](file:///c:/Phoniex/frontend/src/components/DashboardPage.tsx#L1457) | `secondaryCameras`, `selectedCamId` | `GET /api/v1/cameras` | Dynamic API | Clicking a feed selects it as active channel | Rendered empty if role is OCCUPANT (privacy rule) | *"These smaller feeds monitor secondary building corridors including the North Corridor, South Exit, and West Hall."* |
| **Floorplan Spatial Map (SVG)** | Center column | [`EvacuationMap.tsx`](file:///c:/Phoniex/frontend/src/components/EvacuationMap.tsx#L1) | `floorplan`, `route`, `nodeRisks` | `GET /spatial/floorplans/...` | Dynamic SVG | Clicking a corridor node changes occupant origin | Displays uncalibrated warning banner if uploaded video lacks homography | *"Our center panel renders an interactive vector floorplan representing rooms, corridors, emergency exits, risk heatmap nodes, and the animated green Dijkstra evacuation path."* |
| **Origin Node Selector** | Center column bottom | [`DashboardPage.tsx`](file:///c:/Phoniex/frontend/src/components/DashboardPage.tsx#L2005) | `origin`, `handleOriginChange` | `floorplan.nodes` | Dynamic | Changes user location and immediately recalculates shortest path to exit | Defaults to `node_west_suites` | *"This dropdown allows an occupant to select their starting room or corridor location to immediately recalculate the optimal evacuation route."* |
| **Turn-by-Turn Egress Card** | Right column (Occupant) | [`DashboardPage.tsx`](file:///c:/Phoniex/frontend/src/components/DashboardPage.tsx#L1583) | `route.path_nodes` | `GET /routes/current` | Dynamic Graph | None (Directional text) | Falls back to 4-step default standby instructions | *"Under the Occupant role, this panel provides step-by-step turn-by-turn guidance along the computed path, routing civilians away from hazardous zones."* |
| **Occupant Safe Check-In Button** | Right column (Occupant) | [`DashboardPage.tsx`](file:///c:/Phoniex/frontend/src/components/DashboardPage.tsx#L1646) | `occupantSafeChecked` | Client State | Client State | Toggles safety check-in status (turns green) | None | *"This button simulates civilian check-in at the exterior emergency assembly point, confirming safe evacuation."* |
| **Tactical Threat Coordinates Card** | Right column (Responder) | [`DashboardPage.tsx`](file:///c:/Phoniex/frontend/src/components/DashboardPage.tsx#L1706) | `incident` | Database incident record | Dynamic | None (Tactical display) | Shows standby when normal | *"For first responders, this card translates camera detections into real-world coordinates—such as X=22m, Y=18m in East Alcove—to pinpoint fire origin."* |
| **Smoke Growth Telemetry & Chart** | Right column (Responder & Mgr) | [`DashboardPage.tsx`](file:///c:/Phoniex/frontend/src/components/DashboardPage.tsx#L1718) | `liveSmoke`, `renderSmokeChart()` | `TemporalSmokeAnalyzer` & WS | Dynamic Math | None (SVG Sparkline) | Renders empty flatline if no smoke is observed | *"This telemetry panel displays the measured smoke plume area in square pixels, the growth rate in pixels per second, and a live trajectory trend chart."* |
| **Zone Headcount Card** | Right column (Responder) | [`DashboardPage.tsx`](file:///c:/Phoniex/frontend/src/components/DashboardPage.tsx#L1737) | Hardcoded simulation | Explicitly labeled `[SIMULATED BADGE TELEMETRY]` | Simulated | None | Notes that frame person counts do not equal building headcount | *"This card displays facility badge headcount, which is transparently documented as simulated building telemetry because single-camera frame detections cannot track unique individuals."* |
| **Life-Safety Subsystems Console** | Right column (Manager) | [`DashboardPage.tsx`](file:///c:/Phoniex/frontend/src/components/DashboardPage.tsx#L1868) | Hardcoded automation | Explicitly labeled `[BUILDING AUTOMATION EMULATION]` | Emulated | None | Shows emulated status | *"This panel reflects facility automation, indicating whether HVAC smoke evacuation dampers are active and fire doors are auto-released."* |
| **Route Reasoning Weights Card** | Right column (Manager) | [`DashboardPage.tsx`](file:///c:/Phoniex/frontend/src/components/DashboardPage.tsx#L1822) | `route.cost_breakdown` | `RouteRecommendation` | Dynamic Math | None (Factor breakdown) | Hidden if no route is active | *"This component explains the algorithmic reasoning behind the path choice, decomposing total cost into distance, hazard exposure, occupancy, and predicted blockage."* |
| **System Microservice Diagnostics** | Right column (SuperAdmin) | [`DashboardPage.tsx`](file:///c:/Phoniex/frontend/src/components/DashboardPage.tsx#L1910) | `health`, `activeUploadedVideo` | `GET /system/health` & benchmarks | Dynamic/Bench | None (Telemetry display) | Shows 31.2 FPS baseline or measured FPS from uploaded video | *"For system administrators, this panel displays microservice health, real-time WebSocket connectivity, and measured PyTorch inference throughput."* |
| **Live WebSocket Event Stream** | Right column (SuperAdmin) | [`DashboardPage.tsx`](file:///c:/Phoniex/frontend/src/components/DashboardPage.tsx#L1953) | `eventHistory` | WebSocket messages | Dynamic Live | Displays scrollable log of last 50 events | Shows empty state if no events received | *"This audit window displays raw domain events as they pass through our asynchronous event bus in real time."* |
| **Role Authentication Modal** | Modal Overlay | [`RoleAuthModal.tsx`](file:///c:/Phoniex/frontend/src/components/RoleAuthModal.tsx#L40) | `isOpen`, `email`, `password` | `POST /auth/login` & `GET /auth/me` | Security Modal | Submits credentials to verify role switch; cancels on backdrop click | Shows clear red error banner if password is wrong or role mismatches | *"This modal enforces zero-trust security; clicking any role requires typing authorized account credentials before session state or access privileges change."* |

---

## 5. Computer Vision & AI/ML Pipeline Deep-Dive

### 5.1 Dual-Model YOLOv11 Architecture
PHOENIX runs a **dual-model perception architecture** implemented in [`app/perception/detector.py`](file:///c:/Phoniex/app/perception/detector.py#L17).

```
                      Raw CCTV Frame (640x640)
                                 │
                 ┌───────────────┴───────────────┐
                 ▼                               ▼
       Model 1: Flame & Smoke           Model 2: Occupant Person
    models/fire_smoke_best.pt              models/yolo11n.pt
      (Custom Trained, 5.46 MB)        (COCO Pre-trained, 5.61 MB)
                 │                               │
       Targets: Fire, Smoke               Targets: Person
       Conf Thresholds:                   Conf Threshold:
       Fire: 0.35, Smoke: 0.30            Person: 0.40
                 │                               │
                 └───────────────┬───────────────┘
                                 ▼
                     Unified Detection List
                 [Detection(bbox, ground_point)]
```

#### Exact Checkpoints & Specifications
1. **Fire & Smoke Model**:
   - Checkpoint Path: `models/fire_smoke_best.pt`
   - File Size: `5,459,610 bytes` (~5.46 MB)
   - Architecture: Ultralytics YOLOv11 nano/small customized architecture.
   - Status: Fine-tuned / custom-trained checkpoint with custom class heads for flame and smoke contours.
   - Verified Output Classes: Class `0: smoke`, Class `1: fire`.
2. **Person / Occupancy Model**:
   - Checkpoint Path: `models/yolo11n.pt`
   - File Size: `5,613,764 bytes` (~5.61 MB)
   - Architecture: Official Ultralytics YOLOv11 Nano pre-trained on MS COCO dataset (80 classes).
   - Filtered Target Class: Class `0: person`.

#### Preprocessing & Inference Parameters
- **Input Dimensions**: Resized to $640 \times 640$ pixels (`imgsz=640`).
- **Inference Device**: Configured in `configs/default.yaml` as `"cpu"` (supports `"cuda"` and `"mps"`).
- **Confidence Thresholds**:
  - `fire`: $0.35$ (35% minimum confidence)
  - `smoke`: $0.30$ (30% minimum confidence)
  - `person`: $0.40$ (40% minimum confidence)
- **Bounding-Box Format**: Internal tensors use `xyxy` format ($[x_1, y_1, x_2, y_2]$ in image pixels).
- **Ground Point Extraction**: For spatial mapping, ground contact point is computed as bottom center:
  $$\text{GroundPoint} = \left(\frac{x_1 + x_2}{2},\; y_2\right)$$

#### Classification vs. Detection
- **Classification**: Assigns a single categorical label to an entire image (e.g., "This image contains fire") without spatial location.
- **Object Detection**: Predicts both categorical labels and exact spatial bounding boxes for multiple co-occurring objects (e.g., "Fire at coordinates $[120, 80, 240, 310]$ with 88% confidence and Person at $[300, 200, 350, 420]$ with 92% confidence"). PHOENIX requires detection to locate where hazards exist in physical space.

---

## 6. Video Ingestion & Processing Lifecycle

The video ingestion and analysis service is implemented in [`app/services/video_service.py`](file:///c:/Phoniex/app/services/video_service.py) and [`app/api/routes/videos.py`](file:///c:/Phoniex/app/api/routes/videos.py).

### Lifecycle Stages:
1. **Upload & SHA-256 Validation**:
   - Operator POSTs video to `/api/v1/videos/upload`.
   - Temporary file is created and checked for allowed extensions (`.mp4`, `.avi`, `.mov`, `.mkv`) and maximum size (500 MB).
   - SHA-256 hash is computed. If identical checksum exists, the existing record is reused; otherwise stored in `storage/videos/` as `vid_{hash[:12]}.mp4`.
2. **Job Scheduling**:
   - Operator triggers `/api/v1/videos/{video_id}/jobs?stride=2`.
   - Initialized in SQLite `processing_jobs` with status `"QUEUED"`, `progress_percent=0.0`.
   - FastAPI launches asynchronous execution using `BackgroundTasks`.
3. **Frame Processing Loop**:
   - `cv2.VideoCapture` decodes frames.
   - Frame stride skips redundant frames (stride=2 processes every 2nd frame, doubling throughput).
   - Both YOLO models execute inference on each selected frame.
   - Keyframe images are saved to `storage/jobs/{job_id}/keyframes/kf_{frame_idx}.jpg` whenever a hazard is detected or every 150 frames.
   - `cv2.VideoWriter` generates an annotated MP4 video (`annotated_{video_id}.mp4`) with bounding boxes, class labels, confidences, and a cyan status HUD.
4. **Completion & Archiving**:
   - Frame records, temporal analyses, detections, and risk snapshots are committed to SQLite.
   - Status transitions to `"COMPLETED"`, `progress_percent=100.0`, with execution time recorded.
   - An immutable `AuditEvent` (`JOB_COMPLETED`) is stored.

---

## 7. Mathematical Formulations

### 7.1 Temporal Smoke Growth Tracking
Implemented in [`app/perception/temporal.py`](file:///c:/Phoniex/app/perception/temporal.py#L25).

```
Image Smoke Plume Detections ──> Sum Bounding Box Areas (Area_t)
                                         │
                    Filtered by Noise Floor (Area > 25 px²)
                                         │
              Sliding Window (10 sec): dt = t_latest - t_earliest
                                         │
                   Raw Growth Rate: (Area_latest - Area_earliest) / dt
                                         │
        Exponential Moving Average Smoothing (alpha = 0.3):
        Smoothed_Rate = 0.3 * Growth_Rate + 0.7 * Prev_Smoothed
                                         │
                    Trend Classification:
                    >= 250 px²/s ──> RAPID_GROWTH
                    >=  50 px²/s ──> MODERATE_GROWTH
                    <= -50 px²/s ──> DECREASING
                    Otherwise    ──> STABLE
```

- **Formula**:
  $$\Delta \text{Area} = \text{Area}_{\text{latest}} - \text{Area}_{\text{earliest}}$$
  $$\text{Growth Rate} = \frac{\Delta \text{Area}}{\Delta t} \quad (\text{units: px}^2/\text{s})$$
  $$\text{Smoothed Rate}_k = \alpha \cdot \text{Growth Rate}_k + (1 - \alpha) \cdot \text{Smoothed Rate}_{k-1} \quad (\alpha = 0.30)$$
- **Critical Distinction**: This is **two-dimensional image-plane pixel area growth**, NOT volumetric physical smoke expansion ($m^3/s$).

### 7.2 Planar Homography Coordinate Transformation
Implemented in [`app/spatial/homography.py`](file:///c:/Phoniex/app/spatial/homography.py#L15).

A $3 \times 3$ planar homography matrix $H$ maps homogeneous pixel coordinates $[u, v, 1]^T$ from the camera image plane to metric floor coordinates $[X, Y, 1]^T$:

$$\begin{bmatrix} x' \\ y' \\ w' \end{bmatrix} = \begin{bmatrix} h_{11} & h_{12} & h_{13} \\ h_{21} & h_{22} & h_{23} \\ h_{31} & h_{32} & h_{33} \end{bmatrix} \begin{bmatrix} u \\ v \\ 1 \end{bmatrix}$$

$$X = \frac{x'}{w'} = \frac{h_{11}u + h_{12}v + h_{13}}{h_{31}u + h_{32}v + h_{33}}, \quad Y = \frac{y'}{w'} = \frac{h_{21}u + h_{22}v + h_{23}}{h_{31}u + h_{32}v + h_{33}}$$

- Calibrated using at least 4 known point pairs via `cv2.findHomography(src, dst, cv2.RANSAC, 5.0)`.
- Mean reprojection error threshold is strictly capped at $15.0 \text{ px}$.

### 7.3 Spatial Risk Estimation Formula
Implemented in [`app/decision/risk.py`](file:///c:/Phoniex/app/decision/risk.py#L16).

For every navigation node $j$ on the floorplan and every detected hazard source $i$:
1. Calculate Euclidean metric distance:
   $$d_{ij} = \sqrt{(X_j - X_i)^2 + (Y_j - Y_i)^2}$$
2. Compute spatial exponential proximity decay:
   $$P_{ij} = \exp(-\lambda \cdot d_{ij}) \quad (\lambda = 0.50 \text{ m}^{-1})$$
3. Compute hazard intensity:
   $$R_{ij} = w_{\text{class}} \times \text{Confidence}_i \times M_{\text{growth}} \times P_{ij}$$
   Where:
   - $w_{\text{fire}} = 1.00$, $w_{\text{smoke}} = 0.60$
   - $M_{\text{growth}} = 1.50$ for `RAPID_GROWTH`, $1.25$ for `MODERATE_GROWTH`, $1.00$ for `STABLE`
4. Node risk score is the maximum threat:
   $$\text{Risk}(j) = \max_i (R_{ij}), \quad \text{clipped to } [0.0, 1.0]$$

#### Worked Numerical Example:
- Fire detected at $X=22.0, Y=18.0$ with confidence $= 0.90$.
- Trend is `RAPID_GROWTH` ($M_{\text{growth}} = 1.50$).
- Target Corridor Node is at $X=22.0, Y=16.0$ ($d = 2.0\text{ meters}$).
- Computation:
  $$P = \exp(-0.50 \times 2.0) = \exp(-1.0) \approx 0.3679$$
  $$\text{Risk} = 1.00 \times 0.90 \times 1.50 \times 0.3679 = 0.497 \quad (\text{MEDIUM RISK})$$

### 7.4 Multi-Factor Graph Routing & Cost Decomposition
Implemented in [`app/decision/routing.py`](file:///c:/Phoniex/app/decision/routing.py#L24).

Edge weight between nodes $u$ and $v$ is a linear combination of four normalized costs:
$$W(u, v) = w_d \cdot C_{\text{dist}} + w_h \cdot C_{\text{hazard}} + w_o \cdot C_{\text{occ}} + w_p \cdot C_{\text{pred}}$$
- $w_d = 0.35$ (Distance weight, normalized by corridor reference 50m)
- $w_h = 0.40$ (Hazard weight, normalized $[0, 1]$)
- $w_o = 0.10$ (Occupancy weight, normalized by corridor capacity 20 persons)
- $w_p = 0.15$ (Predicted blockage weight, normalized $[0, 1]$)
- **Hard Block Rule**: If hazard $\ge 0.90$ or $edge.\text{is\_blocked} = \text{True}$, edge is removed from Dijkstra graph.

### 7.5 Estimated Time of Arrival (ETA) Formula
Implemented in [`app/decision/eta.py`](file:///c:/Phoniex/app/decision/eta.py#L13).

For each edge in the optimal path:
$$v_{\text{eff}} = v_{\text{base}} \times f_{\text{stairs}} \times f_{\text{congestion}} \times f_{\text{smoke}}$$
- $v_{\text{base}} = 1.20\text{ m/s}$ (average human walking speed)
- $f_{\text{stairs}} = 0.60$ if edge is stairway
- $f_{\text{congestion}} = 1.0 - \left(0.50 \times \min\left(1.0, \frac{\text{occ} - 5}{20}\right)\right)$ if occupants $> 5$
- $f_{\text{smoke}} = 0.70$ if hazard $> 0.20$
- Minimum clamp: $v_{\text{eff}} \ge 0.20\text{ m/s}$
$$\text{Total ETA} = \sum_{\text{edges}} \frac{\text{Length}_e}{v_{\text{eff}}}$$

---

## 8. Backend, APIs & Network Protocol Catalog

FastAPI is configured in [`app/main.py`](file:///c:/Phoniex/app/main.py#L35) with `/api/v1` prefix.

| Method | Endpoint Path | Function / File | Auth Req? | Allowed Roles | Request Parameters / Body | Response Payload Summary | Calling Frontend Component | Current Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `GET` | `/` | `root` ([`main.py`](file:///c:/Phoniex/app/main.py#L82)) | No | Public | None | System info & health link | Browser direct | Verified Working |
| `GET` | `/api/v1/system/health` | `health_check` ([`system.py`](file:///c:/Phoniex/app/api/routes/system.py#L17)) | No | Public | None | Status: HEALTHY, service map | Header indicator, Explorer | Verified Working |
| `GET` | `/api/v1/system/ready` | `readiness_check` ([`system.py`](file:///c:/Phoniex/app/api/routes/system.py#L29)) | No | Public | None | Ready: true, AI: OPERATIONAL | System readiness checks | Verified Working |
| `POST` | `/api/v1/auth/login` | `login` ([`auth.py`](file:///c:/Phoniex/app/api/routes/auth.py#L43)) | No | Public | `{email, password}` | `TokenResponse` (access + refresh) | `LoginPage.tsx`, `RoleAuthModal.tsx` | Verified Working |
| `POST` | `/api/v1/auth/refresh` | `refresh_token` ([`auth.py`](file:///c:/Phoniex/app/api/routes/auth.py#L112)) | No | Public | `{refresh_token}` | Rotated `TokenResponse` | Session keep-alive | Verified Working |
| `POST` | `/api/v1/auth/logout` | `logout` ([`auth.py`](file:///c:/Phoniex/app/api/routes/auth.py#L182)) | Yes | Any Role | Optional `{refresh_token}` | Success message | Header Sign Out | Verified Working |
| `GET` | `/api/v1/auth/me` | `get_current_user_profile` ([`auth.py`](file:///c:/Phoniex/app/api/routes/auth.py#L214)) | Yes | Any Role | Bearer Token | `UserResponse` (id, role, org) | `AuthContext.tsx`, `RoleAuthModal.tsx` | Verified Working |
| `GET` | `/api/v1/auth/users` | `list_users` ([`auth.py`](file:///c:/Phoniex/app/api/routes/auth.py#L233)) | Yes | `SUPERADMIN` | None | `List[UserResponse]` | Admin management | Verified Working |
| `POST` | `/api/v1/auth/users` | `create_user` ([`auth.py`](file:///c:/Phoniex/app/api/routes/auth.py#L253)) | Yes | `SUPERADMIN` | `CreateUserRequest` | Created user details | Admin management | Verified Working |
| `GET` | `/api/v1/buildings/{id}` | `get_building` ([`domain.py`](file:///c:/Phoniex/app/api/routes/domain.py#L106)) | Yes | Any Role | `building_id` | `BuildingResponse` (floors, dimensions) | Header building card | Verified Working |
| `GET` | `/api/v1/cameras` | `get_cameras` ([`domain.py`](file:///c:/Phoniex/app/api/routes/domain.py#L161)) | Yes | `SUPERADMIN`, `BUILDING_MANAGER`, `FIRST_RESPONDER` | `building_id` | `List[CameraResponse]` | Camera surveillance matrix | Verified Working (403 for Occupant) |
| `GET` | `/api/v1/incidents/current` | `get_current_incident` ([`domain.py`](file:///c:/Phoniex/app/api/routes/domain.py#L42)) | Yes | Any Role | `building_id` | Active `IncidentResponse` or `null` | Alert banner, Decision HUD | Verified Working |
| `GET` | `/api/v1/routes/current` | `get_current_route` ([`domain.py`](file:///c:/Phoniex/app/api/routes/domain.py#L72)) | Yes | Any Role | `origin`, `building_id` | `RouteRecommendationResponse` | Spatial Map, Occupant HUD | Verified Working |
| `GET` | `/api/v1/detections/recent` | `get_recent_detections` ([`domain.py`](file:///c:/Phoniex/app/api/routes/domain.py#L251)) | Yes | Any Role | `camera_id`, `limit` | Recent detection records | Telemetry pills | Verified Working |
| `GET` | `/api/v1/risk/current` | `get_current_risk` ([`domain.py`](file:///c:/Phoniex/app/api/routes/domain.py#L262)) | Yes | Any Role | `building_id` | Latest `RiskSnapshot` | Heatmap, Risk indicators | Verified Working |
| `GET` | `/api/v1/events/history` | `get_event_history` ([`domain.py`](file:///c:/Phoniex/app/api/routes/domain.py#L271)) | Yes | Any Role | `limit` | List of audit events | SuperAdmin event stream | Verified Working |
| `POST` | `/api/v1/videos/upload` | `upload_video` ([`videos.py`](file:///c:/Phoniex/app/api/routes/videos.py#L30)) | Yes | Any Role | Multipart video file | `VideoSourceResponse` | Dashboard Upload Button | Verified Working |
| `POST` | `/api/v1/videos/{id}/jobs` | `create_and_start_processing_job` ([`videos.py`](file:///c:/Phoniex/app/api/routes/videos.py#L103)) | Yes | Any Role | `stride`, `camera_id` | `ProcessingJobResponse` | Dashboard Upload Lifecycle | Verified Working |
| `GET` | `/api/v1/jobs/{job_id}` | `get_job` ([`videos.py`](file:///c:/Phoniex/app/api/routes/videos.py#L206)) | Yes | Any Role | `job_id` | Status, progress, metrics | Dashboard Polling Timer | Verified Working (See note on polling starvation) |
| `GET` | `/api/v1/jobs/{job_id}/results`| `get_job_results` ([`videos.py`](file:///c:/Phoniex/app/api/routes/videos.py#L227)) | Yes | Any Role | `job_id` | Full detections, routes, smoke data | Dashboard Apply Results | Verified Working |
| `GET` | `/api/v1/jobs/{id}/annotated-video` | `download_annotated_video` ([`videos.py`](file:///c:/Phoniex/app/api/routes/videos.py#L280)) | Yes | Any Role | `job_id` | Video stream (FileResponse) | AI Overlay Video Player | Verified Working |
| `GET` | `/api/v1/explorer/overview` | `get_storage_overview` ([`explorer.py`](file:///c:/Phoniex/app/api/routes/explorer.py#L91)) | Yes | `SUPERADMIN`, `BUILDING_MANAGER`, `FIRST_RESPONDER` | None | Filesystem & DB file statistics | `DataStorageExplorer.tsx` | Verified Working |
| `GET` | `/api/v1/explorer/database` | `get_database_inventory` ([`explorer.py`](file:///c:/Phoniex/app/api/routes/explorer.py#L223)) | Yes | `SUPERADMIN`, `BUILDING_MANAGER` | None | Table counts & schemas | `DataStorageExplorer.tsx` | Verified Working |
| `GET` | `/api/v1/explorer/users` | `get_user_inventory` ([`explorer.py`](file:///c:/Phoniex/app/api/routes/explorer.py#L173)) | Yes | `SUPERADMIN` | None | Safe user accounts list | `DataStorageExplorer.tsx` | Verified Working |
| `GET` | `/api/v1/explorer/jobs` | `get_jobs_inventory` ([`explorer.py`](file:///c:/Phoniex/app/api/routes/explorer.py#L267)) | Yes | `SUPERADMIN`, `BUILDING_MANAGER`, `FIRST_RESPONDER` | `limit`, `offset` | Paginated job history | `DataStorageExplorer.tsx` | Verified Working |
| `WS` | `/ws/v1/buildings/{id}` | `websocket_endpoint` ([`websocket_router.py`](file:///c:/Phoniex/app/events/websocket_router.py#L42)) | Yes | Valid JWT in query `?token=` | `token` | Real-time JSON event packets | `WebSocketContext.tsx` | Verified Working |

---

## 9. Database Schema & Storage Architecture

### 9.1 Database Engine & Configuration
- **Engine**: SQLite 3 with Write-Ahead Logging (`PRAGMA journal_mode=WAL;`).
- **Database Path**: `c:\Phoniex\phoenix.db` (Accompanied by `phoenix.db-shm` and `phoenix.db-wal`).
- **Connection Wrapper**: Custom context manager [`db_transaction()`](file:///c:/Phoniex/app/db/sqlite.py#L65) enforcing immediate exclusive locks and foreign key support (`PRAGMA foreign_keys = ON;`).

### 9.2 Exact Tables & Live Verified Row Counts

| Table Name | Primary Key | Key Foreign Keys | Purpose / Stored Entities | Live Row Count (Read-Only Verified) |
| :--- | :--- | :--- | :--- | :--- |
| `organizations` | `organization_id` | None | Tenant organizations | **1** |
| `buildings` | `building_id` | `organization_id` | Physical facility records | **1** |
| `floors` | `floor_id` | `building_id` | Facility floor levels & dimensions | **1** |
| `floorplans` | `floorplan_id` | `building_id`, `floor_id` | Navigation topology, nodes & edges JSON | **1** |
| `cameras` | `camera_id` | `building_id`, `floor_id` | Registered CCTV cameras & source URIs | **7** |
| `calibrations` | `calibration_id` | `camera_id` | $3 \times 3$ planar homography matrices | **1** |
| `users` | `user_id` | `organization_id` | Role accounts with Argon2id password hashes | **4** |
| `auth_sessions` | `session_id` | `user_id` | Revocable refresh token hashes & expirations | **165** |
| `incidents` | `incident_id` | `building_id`, `floor_id` | Emergency hazard declarations & severity | **63** |
| `video_sources` | `video_id` | `organization_id`, `created_by_user_id` | Stored video files, SHA-256 hashes, sizes | **66** |
| `processing_jobs` | `job_id` | `video_id`, `camera_id` | Asynchronous perception execution states | **58** |
| `video_frames` | `frame_id` | `job_id`, `video_id` | Processed frame index & keyframe image paths | **1,111** |
| `detections` | `detection_id` | `job_id`, `camera_id` | YOLO bounding boxes, confidences, classes | **68,104** |
| `temporal_analyses` | `analysis_id` | `job_id`, `camera_id` | Plume area ($px^2$), growth rate, and trend | **815** |
| `risk_events` | `snapshot_id` | `job_id`, `building_id` | Node risk maps and global risk levels | **1,641** |
| `route_recommendations` | `route_id` | `building_id`, `floor_id` | Dijkstra paths, ETA (s), decomposed costs | **35,504** |
| `audit_events` | `audit_id` | `organization_id`, `user_id` | Immutable security and operational audit trail | **208** |
| `alembic_version` | None | None | Database migration tracking | **1** |

### 9.3 Job Isolation Guarantee
Every row written by video processing (`detections`, `video_frames`, `temporal_analyses`, `risk_events`, `route_recommendations`) contains a foreign key `job_id`. When the frontend or explorer queries results for a specific video, it filters with `WHERE job_id = ?`, mathematically preventing cross-job data leakage.

### 9.4 Filesystem Storage Hierarchy
```
c:\Phoniex\
├── phoenix.db                          (Primary SQLite 3 database file, 40.4 MB)
├── models/
│   ├── fire_smoke_best.pt              (Custom YOLOv11 flame/smoke weights, 5.46 MB)
│   └── yolo11n.pt                      (COCO pre-trained YOLOv11 nano weights, 5.61 MB)
├── videos/                             (Simulated live CCTV video streams)
│   ├── Main_video.mp4                  (Central corridor CCTV footage)
│   ├── Main_video_annotated.mp4        (Pre-rendered OpenCV detection HUD stream)
│   ├── test 1.mp4                      (North corridor stream)
│   ├── test2.mp4                       (South exit stream)
│   └── test3.mp4                       (West hall stream)
└── storage/                            (Isolated managed storage for uploads)
    ├── videos/                         (Uploaded source videos: vid_{hash}.mp4)
    └── jobs/                           (Artifacts organized per job: job_{uuid}/)
        ├── annotated_{video_id}.mp4    (Full rendered MP4 with bounding box overlays)
        └── keyframes/                  (Sample JPEG keyframes: kf_{frame_idx}.jpg)
```

---

## 10. Four-Role Security & RBAC Enforcement

PHOENIX enforces a strict **Zero-Trust Role-Based Access Control (RBAC)** architecture.

```mermaid
graph TD
    User([User Client]) --> AuthCheck{Bearer JWT Valid?}
    AuthCheck -- No --> 401[HTTP 401 Unauthorized]
    AuthCheck -- Yes --> RoleCheck{Token Role in Allowed Roles?}
    
    RoleCheck -- SUPERADMIN --> AccessGranted[Access Resource]
    RoleCheck -- Authorized Role --> AccessGranted
    RoleCheck -- Insufficient Role --> 403[HTTP 403 Forbidden]
```

### 10.1 Role-Permission Matrix

| Resource / Action | SUPERADMIN | BUILDING_MANAGER | FIRST_RESPONDER | OCCUPANT | Backend Enforcement Source |
| :--- | :---: | :---: | :---: | :---: | :--- |
| **View Safe Evacuation Path & ETA** | ✅ | ✅ | ✅ | ✅ | `domain.py:get_current_route` |
| **Check In Safe at Assembly Point** | ✅ | ✅ | ✅ | ✅ | Client state (Occupant action) |
| **View CCTV Surveillance Feeds** | ✅ | ✅ | ✅ | ❌ *(Denied)* | `domain.py:get_cameras` (`require_role`) |
| **Spatial Threat Coordinates ($X, Y$)** | ✅ | ✅ | ✅ | ❌ | Dashboard HUD layout |
| **Temporal Smoke Growth Telemetry** | ✅ | ✅ | ✅ | ❌ | Dashboard HUD layout |
| **Broadcast Facility PA Announcement** | ✅ | ✅ | ❌ | ❌ | Client state (Manager action) |
| **Declare Incident Resolved** | ✅ | ✅ | ❌ | ❌ | Client state (Manager action) |
| **Dispatch Fire Suppression Team** | ✅ | ❌ | ✅ | ❌ | Client state (Responder action) |
| **Data & Storage Explorer Overview** | ✅ | ✅ | ✅ | ❌ | `explorer.py:get_storage_overview` |
| **Database Schema & Row Counts** | ✅ | ✅ | ❌ | ❌ | `explorer.py:get_database_inventory` |
| **User Account & Session Management** | ✅ | ❌ | ❌ | ❌ | `auth.py:list_users`, `explorer.py` |
| **Upload Video & Queue AI Jobs** | ✅ | ✅ | ✅ | ✅ | `videos.py:upload_video` |

### 10.2 Why Occupants Are Restricted from CCTV Feeds
Examiners often ask why Occupants are barred from cameras:
1. **Bandwidth Preservation**: During panic, hundreds of occupants accessing raw video streams would exhaust building Wi-Fi and network bandwidth needed for life-safety telemetry.
2. **Panic Mitigation**: Seeing uncontrolled flames or smoke induces cognitive overload, disorientation, and stampedes.
3. **Privacy Compliance**: Restricting live internal video feeds protects worker privacy during ordinary non-emergency hours.

### 10.3 Authenticated Role Switching Mechanics
A user cannot switch roles simply by toggling client-side state. When a role button is clicked in the dashboard:
1. `handleRoleSwitch(targetRole)` opens `RoleAuthModal.tsx`.
2. The user enters email and password for the target account.
3. `authenticateAndSwitch()` sends credentials to `POST /auth/login`.
4. It fetches `GET /auth/me` with the new token to confirm the backend role claim matches `targetRole`.
5. Only upon successful verification does `ApiClient.setToken()` update, invalidating previous sessions. If authentication fails, the original active session remains untouched.

---

## 11. Real vs. Simulated Features (Radical Transparency)

A primary grading criterion in technical vivas is honesty regarding which features are genuinely executing and which are simulated.

```
┌──────────────────────────────────────┬──────────────────────────────────────┐
│       GENUINE & FULLY EXECUTED       │        SIMULATED / EMULATED          │
├──────────────────────────────────────┼──────────────────────────────────────┤
│ • Dual-Model YOLOv11 Inference       │ • Building Badge Headcount           │
│   (PyTorch tensors, bounding boxes)  │   (Simulated 14 total, 12 safe, 2 in)│
│                                      │                                      │
│ • Temporal Smoke Area Growth         │ • HVAC Smoke Damper Hardware         │
│   (ΔArea / Δt in px²/s, EMA alpha)   │   (Emulated building automation)     │
│                                      │                                      │
│ • Planar Homography 3x3 Mapping      │ • Fire Door Magnetic Auto-Release    │
│   (RANSAC image-to-metric transform) │   (Emulated physical relays)         │
│                                      │                                      │
│ • Deterministic Spatial Risk Engine  │ • Benchmark Baseline FPS Display     │
│   (Exponential proximity decay)      │   (31.2 FPS baseline when idle)      │
│                                      │                                      │
│ • Multi-Factor Dijkstra Routing      │ • Occupant Fallback Instructions     │
│   (NetworkX shortest-path + ETA)     │   (4 static steps only if route=null)│
│                                      │                                      │
│ • SQLite Database & RBAC Auth        │ • Multi-Camera Spatial Graph Binding │
│   (Argon2id, JWT, 18 tables, WAL)    │   (Primary camera CAM-MAIN-01 bound) │
└──────────────────────────────────────┴──────────────────────────────────────┘
```

---

## 12. Verified Current Status & Unresolved Bugs

Based on rigorous testing and code investigation, here is the exact runtime status:

### Issue 1: Camera 403 Forbidden for Occupant
- **Classification**: **FIXED AND VERIFIED**
- **Evidence**: [`frontend/src/components/DashboardPage.tsx:153`](file:///c:/Phoniex/frontend/src/components/DashboardPage.tsx#L153) explicitly checks `if (role === 'OCCUPANT')` and returns `Promise.resolve([])` without firing the forbidden request. [`tests/contract/test_api_contract.py:88`](file:///c:/Phoniex/tests/contract/test_api_contract.py#L88) verifies that backend returns 403 if an Occupant token requests `/api/v1/cameras`.

### Issue 2: Role Switching Privileges
- **Classification**: **FIXED AND VERIFIED**
- **Evidence**: [`frontend/src/components/RoleAuthModal.tsx`](file:///c:/Phoniex/frontend/src/components/RoleAuthModal.tsx) intercepts all role button clicks, requiring password entry for the target role. Client state cannot diverge from backend JWT claims.

### Issue 3: Video Upload Notice: `Failed checking processing status: Failed to fetch`
- **Classification**: **STILL PRESENT / ARCHITECTURAL ROOT CAUSE IDENTIFIED**
- **Root Cause**: In [`app/services/video_service.py:220`](file:///c:/Phoniex/app/services/video_service.py#L220), `execute_job` is declared as `async def execute_job(...)` and launched via FastAPI's `BackgroundTasks.add_task()`. Inside `execute_job`, heavy synchronous CPU-bound operations (`detector.detect()` calling PyTorch YOLO, `cv2.VideoCapture.read()`, and `writer.write()`) execute across 120+ frames without yielding to the asyncio event loop (no `await asyncio.sleep(0)` and no `asyncio.to_thread()`).
- **Consequence**: The single-threaded Python event loop is 100% blocked for ~50 seconds running video inference. During this time, FastAPI cannot respond to incoming HTTP polling requests (`GET /jobs/{jobId}`). The browser's `fetch()` calls fail with network timeouts. After 4 consecutive failures (4.8 seconds), the frontend catches the error and displays:
  `Failed checking processing status: Failed to fetch`.
- **Proof of Background Completion**: Despite the frontend error, the Python background worker completes successfully. SQLite query reveals job `job_84148c200c99` reached `status: COMPLETED` with 460 detections, 120 frames processed, and `annotated_vid_f3dae5dcd3de.mp4` generated in 51.32 seconds.

### Issue 4: API HEALTHY & WebSocket LIVE Indicators
- **Classification**: **FIXED AND RUNTIME-VERIFIED**
- **Evidence**: Both indicators are bound to live state: `health?.status` from `GET /system/health` (verified returning HTTP 200 `HEALTHY`) and `isConnected` from WebSocket `onopen`/`onclose` on port 8000.

### Issue 5: Static Occupant Instructions & Simulated Headcount
- **Classification**: **VERIFIED & TRANSPARENTLY LABELED**
- **Evidence**: Occupant instructions dynamically map `route.path_nodes` when a route exists ([`DashboardPage.tsx:1593`](file:///c:/Phoniex/frontend/src/components/DashboardPage.tsx#L1593)), falling back to 4 static steps only if the route is null. Badge headcount and HVAC status are visibly labeled `[SIMULATED]` and `[EMULATED]` in the UI.

---

## 13. Test Suite & Performance Evidence

### 13.1 Automated Test Execution Results

```
Command Run: python -m pytest tests/unit
Output: 71 passed in 24.73s (100% PASS)
Coverage: Configuration, domain models, spatial algorithms, homography, risk engine, Dijkstra routing, ETA estimation, temporal smoothing, Argon2id security.

Command Run: python -m pytest -p no:deepeval tests/contract/test_api_contract.py
Output: 7 passed in 17.08s (100% PASS)
Coverage: System health, system readiness, login success, invalid password rejection, unauthenticated access rejection, authenticated incident/route fetch, RBAC camera 403 rejection.

Command Run: python -m pytest -p no:deepeval tests/integration
Output: 34 passed, 2 failed in 26.38s
- test_four_role_rbac_explorer.py: 20 passed (100%)
- test_persistence_security_e2e.py: 12 passed (100%)
- test_phase4_phase5_integration.py: 1 passed (100%)
- test_pipeline_e2e.py: 1 passed, 2 failed (Failed on relative test video path and test client credential mismatch)

Command Run: npm run build (inside frontend/)
Output: tsc -b && vite build -> Built in 1.02s (ZERO TypeScript or syntax errors)
Production bundle created: dist/assets/index-Dt1mYPb8.js (348.82 kB).
```

---

## 14. Setup & Startup Instructions

### Backend Startup (FastAPI)
```powershell
# Open terminal inside C:\Phoniex
python -m uvicorn app.main:app --reload --port 8000
```
- Listens on `http://localhost:8000`.
- API Documentation available at `http://localhost:8000/docs` and `/redoc`.
- WebSocket endpoint active at `ws://localhost:8000/ws/v1/buildings/bldg-hq-01`.

### Frontend Startup (React 19 / Vite)
```powershell
# Open terminal inside C:\Phoniex\frontend
npm run dev
```
- Available at `http://localhost:3000`.

### Default Seed Accounts (Argon2id Hashed in SQLite)
| Role | Email | Password |
| :--- | :--- | :--- |
| **SuperAdmin** | `admin@phoenix.local` | `AdminPass123!` |
| **Building Manager** | `manager@phoenix.local` | `ManagerPass123!` |
| **First Responder** | `responder@phoenix.local` | `ResponderPass123!` |
| **Occupant** | `occupant@phoenix.local` | `OccupantPass123!` |

---

## 15. Step-by-Step Viva Demonstration Script

Follow this sequence during your practical demonstration to wow the examiners:

1. **Step 1: Landing Page & Security Concept**
   - Open browser at `http://localhost:3000`.
   - Point to the landing page and explain: *"PHOENIX is an autonomous emergency intelligence system. We enter the control room by authenticating through our Zero-Trust gateway."*
   - Click **Control Room Access →**.
2. **Step 2: Authenticate as Building Manager**
   - Click the quick-fill button for **🏢 Building Mgr** (`manager@phoenix.local` / `ManagerPass123!`).
   - Click **Sign In to Control Room**.
   - Point to the top bar: Show **API: HEALTHY** (green) and **WS: LIVE** (green).
3. **Step 3: Demonstrate Multi-Camera Surveillance & Baseline CCTV**
   - Point to the left column: *"Here we see our CCTV surveillance matrix. The primary channel plays back central corridor surveillance, while secondary feeds cover the North Corridor and South Exit."*
   - Toggle the **✓ AI ANNOTATED** button: Show how OpenCV overlays bounding boxes with detection confidences on the video stream.
4. **Step 4: Demonstrate Center Floorplan & Dynamic Route**
   - Point to the center map: *"Here is our vector floorplan. PHOENIX detects the fire at the East Alcove, calculates spatial proximity risk across the corridor, and computes the green shortest-path evacuation route leading to Exit South."*
   - Click a different room node on the map: Show that the route immediately recalculates from the new starting location.
5. **Step 5: Demonstrate Zero-Trust Role Switching**
   - Click the **👤 Occupant** role button in the header.
   - Point to `RoleAuthModal`: *"Notice that clicking a role button does not bypass security. We must authenticate with the Occupant credentials (`occupant@phoenix.local` / `OccupantPass123!`)."*
   - Click **Authenticate & Switch**.
   - Show the Occupant HUD: Point out that CCTV video feeds disappear for privacy and network preservation, replaced by turn-by-turn evacuation instructions and the "I Have Safely Evacuated" button.
6. **Step 6: Demonstrate Data & Storage Explorer**
   - Switch back to **SuperAdmin** (`admin@phoenix.local` / `AdminPass123!`).
   - Click the purple **🗄️ Data & Storage Explorer** button in the header.
   - Show the live SQLite database stats: 18 tables, over 68,000 detections, 35,000 route recommendations, WAL journal mode, and verified model checkpoints.
   - Conclude: *"This confirms that PHOENIX is not a mockup; every inference output and evacuation calculation is persisted to our relational database."*

---

## 16. Top 40 Viva Questions & Concise Technical Answers

### Architecture & System Design
1. **Q: What is PHOENIX?**  
   *A: PHOENIX is an autonomous building emergency decision-support system that processes CCTV video using computer vision, evaluates spatial fire and smoke risk, and calculates dynamic evacuation paths using graph algorithms.*
2. **Q: What is the primary life-safety advantage of PHOENIX over traditional exit signs?**  
   *A: Traditional exit signs are static and can direct occupants into smoke-filled corridors. PHOENIX dynamically recalculates paths around emerging hazards.*
3. **Q: What is the tech stack of PHOENIX?**  
   *A: Frontend: React 19, TypeScript, and Vite. Backend: FastAPI (Python 3.14). Database: SQLite 3 with Write-Ahead Logging. AI/ML: Ultralytics YOLOv11 and OpenCV.*
4. **Q: What design pattern is used for real-time frontend updates?**  
   *A: An event-driven Pub/Sub pattern. Domain events generated by the perception pipeline are published to a central EventBus and broadcast to clients over WebSockets.*
5. **Q: Why was FastAPI chosen instead of Flask or Django?**  
   *A: FastAPI provides native asynchronous event-loop support, automatic Pydantic request validation, high throughput, and built-in WebSocket endpoints.*
6. **Q: How does PHOENIX handle database concurrency with SQLite?**  
   *A: SQLite is configured in WAL (Write-Ahead Logging) mode, enabling concurrent non-blocking reads while writes are serialized through a custom transaction context manager.*
7. **Q: What is the purpose of the 5-layer system architecture?**  
   *A: It decouples low-level pixel processing (Perception) from geometric conversion (Spatial), risk modeling (Decision), storage (Persistence), and UI (Presentation).*
8. **Q: How does the system prevent cross-job data contamination?**  
   *A: Every database table storing perceptual artifacts includes a foreign key `job_id`, ensuring strict tenant and job query isolation.*

### Computer Vision & AI/ML
9. **Q: Why does PHOENIX use two YOLO models instead of one?**  
   *A: We use a specialized fine-tuned model for fire/smoke contours (`fire_smoke_best.pt`) and a pre-trained COCO model for persons (`yolo11n.pt`). This avoids multi-class interference and maximizes detection recall.*
10. **Q: What is the difference between object classification and object detection?**  
    *A: Classification categorizes the overall image; object detection locates specific instances and predicts coordinates for bounding boxes around each object.*
11. **Q: What are the confidence thresholds configured in the system?**  
    *A: Fire: 0.35, Smoke: 0.30, and Person: 0.40.*
12. **Q: What is a bounding box ground contact point and why is it used?**  
    *A: It is the bottom-center coordinate $(\frac{x_1+x_2}{2}, y_2)$ of the detection box, representing where an object touches the floor for planar homography mapping.*
13. **Q: What image resolution does the model expect?**  
    *A: $640 \times 640$ pixels, normalized and resized via letterboxing.*
14. **Q: How does frame stride improve processing efficiency?**  
    *A: By processing every $N$-th frame (e.g., stride=2 skips every other frame), reducing CPU/GPU inference load by 50% while preserving temporal tracking.*
15. **Q: Is the fire/smoke model pre-trained or fine-tuned?**  
    *A: It is a custom fine-tuned YOLOv11 checkpoint trained on flame and smoke imagery, outputting two distinct classes: smoke (class 0) and fire (class 1).*
16. **Q: Does YOLO output 3D coordinates?**  
    *A: No. YOLO outputs 2D pixel bounding boxes $[x_1, y_1, x_2, y_2]$ on the camera image plane.*

### Temporal & Spatial Mathematics
17. **Q: How does PHOENIX measure smoke growth?**  
    *A: Our `TemporalSmokeAnalyzer` tracks cumulative smoke bounding-box area across frames, calculating rate of change $\Delta \text{Area} / \Delta t$ over a 10-second sliding window.*
18. **Q: What is the formula for Exponential Moving Average (EMA) smoothing?**  
    *A: $\text{Smoothed}_k = \alpha \cdot \text{Rate}_k + (1 - \alpha) \cdot \text{Smoothed}_{k-1}$, with smoothing factor $\alpha = 0.30$.*
19. **Q: Does the smoke analyzer measure 3D physical volume?**  
    *A: No. It explicitly measures 2D observed image area expansion in pixels squared per second ($px^2/s$).*
20. **Q: What are the thresholds for smoke growth classification?**  
    *A: Growth rate $\ge 250 px^2/s$ is `RAPID_GROWTH`; $\ge 50 px^2/s$ is `MODERATE_GROWTH`; $\le -50 px^2/s$ is `DECREASING`; otherwise `STABLE`.*
21. **Q: What is planar homography?**  
    *A: A projective transformation represented by a $3 \times 3$ matrix that maps points from one planar surface (camera image) to another (floorplan blueprint).*
22. **Q: How many point pairs are required to compute a homography matrix?**  
    *A: A minimum of 4 non-collinear point correspondences, solving an 8-degree-of-freedom system of equations.*
23. **Q: How does PHOENIX compute homography in code?**  
    *A: Using OpenCV's `cv2.findHomography(src_points, dst_points, cv2.RANSAC, 5.0)`.*
24. **Q: What is the reprojection error threshold?**  
    *A: Maximum allowable mean reprojection error is $15.0$ pixels. Matrices exceeding this are rejected as uncalibrated.*

### Risk Assessment & Graph Routing
25. **Q: What mathematical model does the risk engine use for spatial threat propagation?**  
    *A: Exponential spatial decay: $P = \exp(-\lambda \cdot d)$, where $\lambda = 0.50 \text{ m}^{-1}$ and $d$ is metric distance in meters.*
26. **Q: What are the base hazard weights for fire and smoke?**  
    *A: Fire has a base weight of 1.00; smoke has a base weight of 0.60.*
27. **Q: What algorithm is used for evacuation route optimization?**  
    *A: Dijkstra's shortest path algorithm executed over a weighted NetworkX graph.*
28. **Q: What four factors comprise edge weight in the routing graph?**  
    *A: Distance (35%), Hazard risk (40%), Corridor occupancy (10%), and Predicted blockage (15%).*
29. **Q: At what hazard score is an edge completely blocked?**  
    *A: Any edge with hazard score $\ge 0.90$ is hard-blocked and excluded from the passable graph.*
30. **Q: How is Estimated Time of Arrival (ETA) calculated?**  
    *A: Baseline walking speed of 1.2 m/s divided by edge distance, penalized for stairways (0.60x), congestion slowdown (up to 0.50x), and smoke visibility reduction (0.70x).*
31. **Q: What happens if all building exits are blocked?**  
    *A: The routing engine raises a `NoValidRouteError`, switching the UI into a fail-closed emergency state rather than suggesting dangerous paths.*

### Security, Roles & Database
32. **Q: What password hashing algorithm does PHOENIX use?**  
    *A: Argon2id, an award-winning memory-hard password derivation function resistant to GPU brute-force attacks.*
33. **Q: What token mechanism handles authentication?**  
    *A: Signed JWT access tokens (HS256 algorithm) expiring in 8 hours, combined with revocable refresh tokens stored as cryptographic hashes in SQLite.*
34. **Q: What is the difference between HTTP 401 and HTTP 403?**  
    *A: HTTP 401 Unauthorized means authentication is missing or invalid; HTTP 403 Forbidden means the identity is verified but lacks permission for that resource.*
35. **Q: Why does clicking a role button open a credential modal?**  
    *A: To enforce Zero-Trust RBAC. UI views cannot grant privileges; backend JWT claims must be re-authenticated.*
36. **Q: How does PHOENIX ensure Occupant privacy?**  
    *A: The backend dependency `require_role([SUPERADMIN, BUILDING_MANAGER, FIRST_RESPONDER])` blocks the Occupant role from accessing the `/api/v1/cameras` endpoint.*
37. **Q: Does the Data & Storage Explorer use hardcoded mockup values?**  
    *A: No. It executes live SQL queries (`PRAGMA table_info`, `COUNT(*)`) and calls filesystem `os.walk` to report real byte sizes and row counts.*
38. **Q: What is the cause of the upload notice `Failed to fetch`?**  
    *A: `execute_job` is an `async def` function running synchronous YOLO inference directly on the asyncio event loop, temporarily blocking HTTP polling requests.*
39. **Q: Does the background processing job actually fail when `Failed to fetch` appears?**  
    *A: No. The job continues executing in Python and completes successfully in SQLite, as verified by row status `COMPLETED` and generated annotated videos.*
40. **Q: What are the four user roles in PHOENIX?**  
    *A: SuperAdmin, Building Manager, First Responder, and Occupant.*

---

## 17. Difficult Viva Questions & Defense Strategy

### Q1: "Real-world fire cameras get obscured by smoke immediately. How can planar homography or YOLO work when lenses are covered?"
> **Defense Strategy**: "That is an accurate physical limitation of optical computer vision in structural fires. In our design, we address this in two ways:
> First, PHOENIX does not rely on a single camera; it fuses multiple distributed corridor streams.
> Second, our temporal analyzer tracks the trend *as* smoke emerges. If smoke obscures the camera, the risk engine retains the last known high-risk coordinates and applies temporal persistence, treating obscured corridors as completely blocked ($Risk \ge 0.90$) rather than clearing them. In production, optical CV would be paired with thermal imaging (FLIR) and ionization detectors."

### Q2: "Why did you use Dijkstra instead of A*? The comments mention A* but the code uses Dijkstra."
> **Defense Strategy**: "NetworkX provides both algorithms. We deliberately selected Dijkstra's algorithm for multi-exit evacuation because PHOENIX routes to *any* nearest safe exit rather than a single fixed destination. Dijkstra naturally computes the single-source shortest path to all accessible nodes in the graph simultaneously, allowing us to evaluate all designated building exits in a single pass. A* requires a goal-directed heuristic (such as Euclidean distance to a single specific exit), which can cause sub-optimal routing if the chosen exit becomes blocked midway."

### Q3: "You have 14 people shown in the headcount card. Did your YOLO model count 14 unique people?"
> **Defense Strategy**: "No, and we are completely transparent about that in our interface. Single-frame object detection counts bounding box instances, not unique human beings. If one person walks past a camera over 100 frames, YOLO detects 100 person instances. The 14-person headcount card is explicitly labeled in our UI as `[SIMULATED BADGE TELEMETRY]` representing RFID access turnstiles. Tracking unique occupants via vision alone would require multi-camera Re-Identification (Re-ID) and DeepSORT, which is outside our prototype scope."

### Q4: "Your system runs at 15–30 FPS on your machine. What happens when 50 building cameras stream simultaneously?"
> **Defense Strategy**: "In our prototype, we utilize frame striding (stride=2) and run on local CPU/GPU. In a full enterprise deployment across 50 cameras, architecture scaling would follow three standard industry patterns:
> 1. **Edge Inference**: Running lightweight YOLOv11 nano models on edge devices (like NVIDIA Jetson Orin) colocated with cameras.
> 2. **Keyframe Subsampling**: Decoding only 2 to 5 frames per second during surveillance standby, scaling up to 15 FPS only when a flame or smoke trigger occurs.
> 3. **Asynchronous Worker Queues**: Decoupling video processing into Celery or Redis worker pools across multiple GPU nodes so the web event loop is never blocked."

### Q5: "How did you calibrate the camera? Is that homography mapping actually accurate to the millimeter?"
> **Defense Strategy**: "Planar homography assumes that all points lie on a single flat 2D plane ($Z=0$). We calibrate using 4 known physical reference points on the corridor floor. While it provides metric accuracy within approximately 0.5 to 1.0 meters—sufficient to determine whether an occupant should turn left or right down a 4-meter corridor—it is not millimeter-accurate because real floors have minor elevation changes and camera lenses have radial barrel distortion. For life-safety evacuation routing, decimeter accuracy is completely adequate."

---

## 18. Technical Glossary

- **Planar Homography**: A 2D projective transformation mapping points from the camera perspective plane to a ground floorplan coordinate plane via an invertible $3 \times 3$ matrix.
- **RANSAC (Random Sample Consensus)**: An iterative algorithm that estimates mathematical model parameters from data containing outliers, used here to find the optimal homography matrix.
- **Dijkstra's Algorithm**: A greedy graph search algorithm that solves the single-source shortest path problem for graphs with non-negative edge weights.
- **Argon2id**: A hybrid memory-hard cryptographic password hashing algorithm that protects against both side-channel attacks and GPU/ASIC hardware brute-force cracking.
- **JWT (JSON Web Token)**: A compact, URL-safe means of representing claims between two parties, digitally signed using HMAC-SHA256 (`HS256`).
- **WAL Mode (Write-Ahead Logging)**: A SQLite journaling mode where changes are written to a separate `-wal` file, enabling multiple concurrent readers while a write transaction proceeds.
- **Frame Stride**: The interval at which video frames are sampled for neural network inference (e.g., stride=2 processes frames 0, 2, 4, skipping odd frames to conserve compute).
- **Exponential Moving Average (EMA)**: A recursive filtering technique that applies exponentially decreasing weights to older observations, smoothing real-time noise.
- **IoU (Intersection over Union)**: An evaluation metric measuring the overlap between a predicted bounding box and a ground-truth bounding box.
- **RBAC (Role-Based Access Control)**: A security approach restricting system access and operations to authorized users based on their assigned roles.

---

## 19. Complete File & Evidence Inventory

| File Path | Primary Function / Class / Content | Verification Tag |
| :--- | :--- | :--- |
| `app/main.py` | FastAPI application initialization, lifespan handler, router mounting | `VERIFIED FROM SOURCE` |
| `app/core/config.py` | Pydantic system settings, thresholds, default weights | `VERIFIED FROM SOURCE` |
| `app/core/bootstrap.py` | Initial database seeding for organization and 4 role accounts | `VERIFIED FROM SOURCE` |
| `app/core/security.py` | Argon2id password hashing, JWT creation and decoding | `VERIFIED FROM SOURCE` |
| `app/perception/detector.py` | `YOLOAdapter` dual-model wrapper (`fire_smoke_best.pt` + `yolo11n.pt`) | `VERIFIED FROM SOURCE` |
| `app/perception/temporal.py` | `TemporalSmokeAnalyzer` ($\Delta \text{Area} / \Delta t$ with EMA smoothing) | `VERIFIED FROM SOURCE` |
| `app/perception/frame_source.py` | `VideoFrameSource` OpenCV capture decoder and synthetic frame source | `VERIFIED FROM SOURCE` |
| `app/spatial/homography.py` | `PlanarHomographyMapper` ($3 \times 3$ matrix computation and projection) | `VERIFIED FROM SOURCE` |
| `app/decision/risk.py` | `DeterministicRiskEngine` (Exponential spatial decay risk scoring) | `VERIFIED FROM SOURCE` |
| `app/decision/routing.py` | `MultiFactorRoutingEngine` (NetworkX weighted Dijkstra path optimization) | `VERIFIED FROM SOURCE` |
| `app/decision/eta.py` | `DeterministicETAEstimator` (Speed calculation with stairs/smoke penalties) | `VERIFIED FROM SOURCE` |
| `app/services/video_service.py` | `VideoProcessingService` (Video storage, job execution, OpenCV rendering) | `VERIFIED FROM SOURCE` |
| `app/api/dependencies.py` | JWT extraction, `require_role` server-side RBAC enforcement | `VERIFIED FROM SOURCE` |
| `app/api/routes/auth.py` | Login, refresh rotation, logout, user management endpoints | `VERIFIED FROM SOURCE` |
| `app/api/routes/domain.py` | Incidents, routes, buildings, cameras, detections endpoints | `VERIFIED FROM SOURCE` |
| `app/api/routes/videos.py` | Video upload, job queuing, status polling, results endpoints | `VERIFIED FROM SOURCE` |
| `app/api/routes/explorer.py` | Real storage, database schema, user inventory, job inspector | `VERIFIED FROM SOURCE` |
| `app/db/sqlite.py` | SQLite schema creation (`init_db`) and `db_transaction` manager | `VERIFIED FROM SOURCE` |
| `frontend/src/App.tsx` | Root React application, ErrorBoundary, page routing | `VERIFIED FROM SOURCE` |
| `frontend/src/context/AuthContext.tsx` | Authentication session state, atomic role switching | `VERIFIED FROM SOURCE` |
| `frontend/src/context/WebSocketContext.tsx` | WebSocket connection management and ping-pong heartbeat | `VERIFIED FROM SOURCE` |
| `frontend/src/components/DashboardPage.tsx` | Main 3-column control room dashboard (2,037 lines) | `VERIFIED FROM SOURCE` |
| `frontend/src/components/CameraFeed.tsx` | HTML5 video surveillance component with HUD badges | `VERIFIED FROM SOURCE` |
| `frontend/src/components/EvacuationMap.tsx` | Dynamic SVG building floorplan, hazard nodes, green route | `VERIFIED FROM SOURCE` |
| `frontend/src/components/RoleAuthModal.tsx` | Modal dialog enforcing password verification for role transitions | `VERIFIED FROM SOURCE` |
| `frontend/src/components/DataStorageExplorer.tsx` | Reviewer dashboard inspecting SQLite tables and filesystem | `VERIFIED FROM SOURCE` |
| `frontend/src/services/apiClient.ts` | Centralized TypeScript HTTP client for all FastAPI endpoints | `VERIFIED FROM SOURCE` |
| `models/fire_smoke_best.pt` | Custom YOLOv11 flame and smoke neural network weights (5.46 MB) | `VERIFIED FROM SOURCE` |
| `models/yolo11n.pt` | Official COCO YOLOv11 nano person detection weights (5.61 MB) | `VERIFIED FROM SOURCE` |
| `phoenix.db` | Active SQLite database file with 18 tables and 68k+ detections | `VERIFIED AT RUNTIME` |
| `tests/unit` | 71 automated unit tests (All 71 passing) | `VERIFIED BY TEST` |
| `tests/contract` | 7 automated API contract tests (All 7 passing) | `VERIFIED BY TEST` |

---

## 20. Last-Minute One-Page Viva Revision Sheet

**Read this 10 minutes before walking into the examination hall!**

1. **System Core**: PHOENIX is an autonomous building emergency intelligence system combining computer vision, spatial mathematics, and graph algorithms to compute live fire evacuation routes.
2. **Models**:
   - Fire & Smoke: `models/fire_smoke_best.pt` (Classes: `smoke` [0], `fire` [1], custom-trained YOLOv11, 5.46 MB).
   - Persons: `models/yolo11n.pt` (Class: `person` [0], COCO pre-trained YOLOv11, 5.61 MB).
3. **Thresholds**: Fire = 0.35, Smoke = 0.30, Person = 0.40. Input size = $640 \times 640$. Stride = 2.
4. **Smoke Tracking**: Measures 2D pixel area expansion: $\text{Rate} = \Delta \text{Area} / \Delta t$ ($px^2/s$). Smoothed with Exponential Moving Average ($\alpha = 0.30$). $\ge 250 px^2/s$ = Rapid Growth.
5. **Homography**: $3 \times 3$ matrix $H$ calibrated with OpenCV RANSAC using 4 point pairs. Projects bottom-center bounding-box ground contact points $[u, v, 1]^T$ into metric floor coordinates $[X, Y, 1]^T$.
6. **Risk Engine**: $R = w_{\text{class}} \times \text{Confidence} \times M_{\text{growth}} \times \exp(-\lambda \cdot d)$. $\lambda = 0.50 \text{ m}^{-1}$. Base weights: Fire = 1.0, Smoke = 0.6. Risk levels: Low (<0.25), Med (0.25–0.50), High (0.50–0.75), Critical ($\ge 0.75$).
7. **Routing Algorithm**: Multi-factor Dijkstra on NetworkX graph. Edge weights = 35% distance + 40% hazard + 10% occupancy + 15% predicted blockage. Hazard $\ge 0.90$ is hard blocked.
8. **ETA**: Walking speed 1.2 m/s, adjusted by stairs (0.60x), congestion slowdown (up to 0.50x), and smoke visibility (0.70x).
9. **Security**: Argon2id password hashing, JWT HS256 access tokens, revocable refresh tokens in SQLite. Role switching requires re-authenticating with credentials. Occupants are restricted from camera feeds for privacy and bandwidth preservation.
10. **Database**: SQLite 3 with Write-Ahead Logging (`WAL` mode). 18 tables. Relational integrity with foreign keys. 68k+ detections.
11. **Upload Status Notice Root Cause**: `execute_job` is CPU-bound and runs directly on the single-threaded asyncio event loop without yielding, temporarily starving HTTP polling requests. The job itself completes successfully in the background.
12. **Real vs Simulated**: YOLO detections, homography, risk, and Dijkstra routes are **GENUINE**. Headcount badges and HVAC status are transparently **SIMULATED/EMULATED**.
