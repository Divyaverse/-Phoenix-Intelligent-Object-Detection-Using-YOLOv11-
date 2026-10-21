# PHOENIX Real Video Inference Report: `videos/Main_video.mp4`

## 1. Executive Summary
- **Source Video**: `videos/Main_video.mp4` (1280x720 @ 24.0 FPS, 10.0s)
- **Pipeline Executed**: Dual-Model YOLO Inference (`fire_smoke_best.pt` + `yolo11n.pt`) &rarr; Temporal Smoke Analysis (Delta area / Delta t) &rarr; Planar Homography ($3 \times 3$) &rarr; Deterministic Risk Engine &rarr; NetworkX Multi-Factor Evacuation Routing &rarr; ETA Estimation.
- **Annotated Output**: `videos/Main_video_annotated.mp4`
- **Processing Rate**: 4.5 FPS (Mean latency: 200.33 ms)

---

## 2. Quantitative Detection Statistics

| Class | Total Detections | Frames with Detection | Average Confidence | Detection Characteristics |
| :--- | :---: | :---: | :---: | :--- |
| **FIRE** | 692 | 240 / 240 | 0.619 | Sustained flame on east corridor wall and high-intensity cabinet fire in east alcove. |
| **SMOKE** | 186 | 181 / 240 | 0.533 | Upper corridor ceiling accumulation billowing southward toward camera. |
| **PERSON** | 39 | 37 / 240 | 0.511 | Transient reflections/features detected with low persistence. |

---

## 3. Spatial & Homography Ground-Contact Calibration
- **Camera View**: `CAM-MAIN-01` (Central Corridor North View)
- **Floor-Plane Reprojection Error**: `0.0000 pixels` (PASSED &le; 15.0px threshold)
- **Conditioning**: Non-singular $3 \times 3$ planar homography matrix verified.
- **Physical Hazard Ground Coordinates**:
  - Corridor Junction Fire: mapped to floor metric coordinates $(x \approx 21.2\text{m}, y \approx 22.7\text{m})$.
  - East Alcove Fire: mapped to $(x \approx 34.9\text{m}, y \approx 42.5\text{m})$.
  - Smoke Layer: Confined to ceiling layer ($y \le 300\text{px}$), properly decoupled from planar ground homography to avoid out-of-plane distortion.

---

## 4. Evacuation Guidance & Dynamic Route Optimization
- **Monitored Origin**: `node_west_suites` (Occupant zone on west side of hallway)
- **Route Selection**:
  - North hallway and East alcove are heavily penalized due to active fire ($R = 1.0$) and temporal smoke growth.
  - Safe Route Recommended: `node_west_suites` &rarr; `node_corridor_mid` &rarr; `node_corridor_south` &rarr; `exit_south`.
  - Recommended Exit: **`exit_south` (South Lobby Primary Exit)**.
  - Estimated Evacuation Time: $\approx 15.0\text{ seconds}$.

---

## 5. Artifacts & Outputs
1. **Annotated Video**: `videos/Main_video_annotated.mp4`
2. **Frontend Copy**: `frontend/public/videos/Main_video_annotated.mp4`
3. **Detection Logs**: `evaluation/main_video_validation/detections.json`
4. **Processing Telemetry**: `evaluation/main_video_validation/statistics.json`
