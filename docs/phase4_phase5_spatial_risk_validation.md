# PHOENIX Phase 4 + Phase 5 Validation Document

## 1. Architecture Overview
This document records the verification and validation of **Phase 4 (Robust Spatial Homography Mapping)** and **Phase 5 (Spatial Risk Engine & Heatmap Generation)**.

```
Detection BoundingBox
      ↓
Representative Ground Point (bbox.ground_point = (x1+x2)/2, y2)
      ↓
PlanarHomographyMapper (3x3 RANSAC Homography Matrix H)
      ↓
Floorplan Point2D (x, y) meters
      ↓
DeterministicRiskEngine (Proximity Decay exp(-λ * dist))
      ↓
RiskSnapshot & SpatialHeatmapGenerator (2D Gaussian Raster Grid)
```

---

## 2. Phase 4 Implementation Details

### Representative Point Selection
For object detections (`fire`, `smoke`, `person`), the contact point with the floor is represented by `bbox.ground_point` (`x=(x1+x2)/2.0, y=y2`), representing the bottom-center of the bounding box where object feet/base intersect the physical ground plane.

### Coordinate Conventions & Units
- **Image Space**: $(u, v)$ pixels, origin $(0,0)$ at top-left corner.
- **Floorplan Space**: $(x, y)$ meters, origin $(0,0)$ at top-left corner of the metric floorplan grid.
- **Transform Equation**: Homogeneous perspective transform $[x', y', w']^T = H \cdot [u, v, 1]^T$, where $x = x'/w', y = y'/w'$.

### Calibration Validation & Edge Cases
- **Minimum Correspondences**: Requires $\ge 4$ non-collinear point pairs (`min_calibration_points: 4`).
- **Reprojection Error**: Rejects matrices exceeding `reprojection_error_threshold: 15.0`.
- **Degeneracy & Singularity**: Rejects singular matrices ($\text{det}(H) < 1e-8$) or division by zero ($w \to 0$).
- **Failures**: Raises `InvalidCalibrationError` or `SpatialMappingUnavailableError`.
- **Out-of-Bounds Mapping**: Points outside the camera image boundaries map deterministically to metric floorplan space without crashing.

---

## 3. Phase 5 Risk Model & Heatmap Behavior

### Spatial Risk Engine
- **Proximity Decay**: Exponential spatial decay factor $\text{Factor} = e^{-\lambda \cdot d}$ with $\lambda = 0.5$.
- **Base Hazard Weights**: Fire = 1.0, Smoke = 0.6.
- **Temporal Growth Multiplier**: `RAPID_GROWTH` smoke multiplies hazard intensity by 1.5x.
- **Bounded Range**: Risk per node is strictly clipped to $[0.0, 1.0]$.
- **Zero-Detection Safety**: Empty detections yield $0.0$ risk for all nodes and `LOW` global risk level.

### Spatial Heatmap Raster Grid
- **Resolution**: Configurable grid resolution (default $0.5\text{ m}$).
- **Gaussian Kernel Decay**: Intensity decay $\text{Influence} = I \cdot e^{-d^2 / (2\sigma^2)}$ with $\sigma = \text{decay\_radius} / 2.0$.
- **Determinism**: Identical hazard inputs produce identical 2D raster matrices.

---

## 4. Test Results

### Executed Test Commands
`python -m pytest tests/unit/test_homography.py tests/unit/test_risk_engine.py tests/unit/test_phase4_phase5_spatial_risk.py tests/integration/test_phase4_phase5_integration.py`

**Results**: **16 / 16 PASSED in 0.84s**

- `tests/unit/test_homography.py`: 3 passed
- `tests/unit/test_risk_engine.py`: 3 passed
- `tests/unit/test_phase4_phase5_spatial_risk.py`: 9 passed
- `tests/integration/test_phase4_phase5_integration.py`: 1 passed

---

## 5. Files Created / Modified
1. `tests/unit/test_phase4_phase5_spatial_risk.py` *(New unit test file)*
2. `tests/integration/test_phase4_phase5_integration.py` *(New focused end-to-end integration test file)*
3. `docs/phase4_phase5_spatial_risk_validation.md` *(This documentation file)*

---

## 6. Known Limitations
- Homography assumes a 2D planar ground surface (single floor level).
- Risk decay parameters ($\lambda$, base weights) are research parameters configured in `configs/default.yaml`.
