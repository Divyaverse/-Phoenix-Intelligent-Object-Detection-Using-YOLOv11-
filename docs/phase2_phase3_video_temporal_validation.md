# PHOENIX Phase 2 + Phase 3 Validation Document

## 1. Overview & Goal
This document records the completion and verification of **Phase 2 (Dual-Model Perception Integration)** and **Phase 3 (Temporal Smoke Analysis)** for the PHOENIX emergency intelligence platform.

---

## 2. Phase 2: Dual-Model YOLO Perception Integration
**Status**: **COMPLETED USING PREVIOUSLY VALIDATED YOLO EVIDENCE**

### Evidence Reference
Phase 2 dual-model perception validation was performed using:
- **Fire/Smoke Model**: `models/fire_smoke_best.pt`
- **Person Model**: `models/yolo11n.pt`
- **Verification Evidence**: Artifacts saved in `evaluation/dual_model_validation/` (including `FINAL_REPORT.md`, `summary.csv`, `results.csv`, and annotated frames).

### Interface & Pipeline Compatibility
The interface compatibility of the perception stage was verified:
- **`VideoFrameSource`** emits standard `(success: bool, frame: np.ndarray, timestamp_seconds: float)` tuples.
- **`YOLOAdapter.detect(...)`** accepts frame, `frame_id`, `camera_id`, and `timestamp_seconds` and returns a list of domain `Detection` objects (`fire`, `smoke`, `person`).
- **`TemporalSmokeAnalyzer.process_observations(...)`** ingests the camera ID, detection list, and frame timestamp to produce structured `SmokeObservation` objects.

---

## 3. Phase 3: Temporal Smoke Growth Analysis Validation
**Status**: **COMPLETED**

### Temporal Analytics Rules Verified
1. **Area Calculation**: Computes 2D bounding box area ($\sum w_i \times h_i$ in $\text{px}^2$) for `smoke` class detections.
2. **Noise Floor Filtering**: Bounding box area below `noise_area_filter_px2` ($25\text{ px}^2$) is filtered out.
3. **Sliding Time Window**: Historical records older than `history_window_seconds` ($10.0\text{ s}$) are pruned.
4. **Exponential Moving Average (EMA)**: Smooths instantaneous growth rate ($\Delta\text{area} / \Delta t$) using $\alpha = 0.3$.
5. **Trend Classification**:
   - `RAPID_GROWTH`: Smoothed rate $\ge 250\text{ px}^2/\text{s}$
   - `MODERATE_GROWTH`: Smoothed rate $\ge 50\text{ px}^2/\text{s}$
   - `STABLE`: Growth rate between $-50$ and $+50\text{ px}^2/\text{s}$
   - `DECREASING`: Smoothed rate $\le -50\text{ px}^2/\text{s}$
   - `UNKNOWN`: Insufficient history window ($< 2$ frames)

---

## 4. Test Results

### Test Suite Execution
Executed command:
`python -m pytest tests/unit/test_perception.py tests/unit/test_temporal.py tests/unit/test_perception_temporal_integration.py`

**Results**: **9 / 9 passed in 0.60s**

- `tests/unit/test_perception.py`: 4 passed
- `tests/unit/test_temporal.py`: 4 passed
- `tests/unit/test_perception_temporal_integration.py`: 1 passed

---

## 5. Files Created / Modified
1. `tests/unit/test_perception_temporal_integration.py` *(New combined integration test)*
2. `docs/phase2_phase3_video_temporal_validation.md` *(This validation document)*

---

## 6. Remaining Gaps before Phase 4
- Spatial projection homography mapping (`PlanarHomographyMapper`) to transform pixel ground points to physical metric floorplan coordinates.
