# PHOENIX System Limitations & Assumptions

## 1. Prototype Status & Safety Boundaries

1. **Non-Certified Prototype**: PHOENIX is an AI decision-support research prototype. It is **NOT** a certified life-safety system, a replacement for NFPA/EN54 fire alarm standards, or a guarantee of safe evacuation.
2. **Deterministic Fail-Closed Behavior**: When AI perception is unavailable, camera feeds drop, or calibration is invalid, PHOENIX enters explicit degraded states (`AI_DEGRADED`, `CAMERA_OFFLINE`, `SPATIAL_MAPPING_UNAVAILABLE`) rather than emitting hallucinated emergency advice.
3. **No LLM Decision Authority**: Evacuation routes are computed deterministically using graph algorithms (Dijkstra/A*). Large Language Models are strictly prohibited from selecting or overriding evacuation routes.

## 2. Technical Limitations

| Component | Limitation | Mitigation |
| :--- | :--- | :--- |
| **YOLO Perception** | Optical camera detections are subject to lighting changes, camera glare, and visual occlusion. Smoke opacity and texture vary across materials. | Multi-frame temporal filtering, confidence thresholds, explicit status reporting. |
| **Temporal Growth** | Growth rates represent 2D bounding box and segmented pixel area changes over time ($\Delta \text{area} / \Delta t$), **not** physical 3D volumetric smoke velocities. | Explicitly labeled as "smoke-region growth rate" in all APIs and documentation. |
| **Homography Mapping** | Planar homography assumes ground-level projection. Height disparities (e.g. smoke rising to ceilings) introduce spatial distortion. | Floor-plane calibration with representative footprint points; invalid calibrations reject mapping. |
| **Occupancy** | Visual person detections estimate approximate headcounts, not certified crowd densities or mass evacuation dynamics. | Occupancy signal is normalized and labeled as "approximate occupancy". |
| **ETA Calculation** | Travel time models use empirical walking velocity and penalty factors (stairs, congestion), not micro-simulation of crowd panic. | Assumptions are documented, exposed in configuration, and audited per route. |
| **Persistence & Realtime** | SQLite prototype provides local persistence; WebSockets deliver realtime broadcasts. Realtime delivery does not wait for database disk writes. | In-memory event bus decouples WebSocket broadcasts from SQLite transactions. |
