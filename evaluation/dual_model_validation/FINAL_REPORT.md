# PHOENIX Dual-Model Perception Final Validation Report

## 1. Models Tested
- **Fire/Smoke Model**: `models/fire_smoke_best.pt` (Classes: `smoke`, `fire`)
- **Person Model**: `models/yolo11n.pt` (Classes: COCO `person`)
- **Combined Adapter**: `app.perception.detector.YOLOAdapter`

## 2. Videos Tested
1. `videos/test 1.mp4` (Resolution: 1920x1080)
2. `videos/test2.mp4` (Resolution: 3840x2160)
3. `videos/test3.mp4` (Resolution: 2160x3840)

## 3. Sampling Methodology
- 10 evenly distributed frames per video were evaluated.
- Annotated bounding box images saved to `evaluation/dual_model_validation/<video_name>/`.

## 4. Detection Statistics Summary

| Video | Frames Tested | Fire Frames | Smoke Frames | Person Frames | Fire Detections | Smoke Detections | Person Detections | Avg Fire Conf | Avg Smoke Conf | Avg Person Conf |
| :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| test1 | 10 | 0 | 0 | 9 | 0 | 0 | 60 | 0.0000 | 0.0000 | 0.5109 |
| test2 | 10 | 4 | 7 | 10 | 5 | 7 | 69 | 0.4682 | 0.6434 | 0.6374 |
| test3 | 10 | 9 | 4 | 10 | 13 | 7 | 56 | 0.6271 | 0.4562 | 0.6706 |

## 5. Per-Video Observations
- **test1**: Clear indoor corridor scene. Person model detected occupants accurately across frames (conf 0.40 - 0.65). No fire or smoke detected.
- **test2**: High-resolution wide corridor/hall scene. Large flame detected (conf 0.38 - 0.48) with minor bounding box overlap due to flame flicker. Multiple occupants detected reliably (conf 0.50 - 0.90).
- **test3**: Vertical aspect video feed. Fire hazard detected clearly (conf 0.74). High-confidence person detections (conf 0.70 - 0.82).

## 6. Examples of Detections
- `test2` Frame 0: `fire` (conf 0.4722), `person` (conf 0.8983).
- `test3` Frame 0: `fire` (conf 0.7423), `person` (conf 0.8252).
- `test1` Frame 0: `person` (conf 0.6153).

## 7. False-Positive Observations
- Minor overlapping bounding boxes for wide flame regions in `test2` (2 overlapping fire boxes around the same flame source).

## 8. Missed-Detection Observations
- No obvious missed occupant detections at confidence threshold $\ge 0.40$.

## 9. Duplicate/Overlapping Detections
- Single fire source in `test2` triggered 2 slightly offset bounding boxes (`fire` conf 0.4722 and 0.3756). Non-Maximum Suppression (NMS) within Ultralytics handles most overlaps, but close multi-scale anchors can yield adjacent bounding boxes.

## 10. Dual-Model Adapter Verification
- **Model Loading**: Both weights loaded without error.
- **Data Object**: 100% of returned objects are valid domain `app.domain.models.Detection` instances.
- **Class Normalization**: Emitted classes strictly restricted to `fire`, `smoke`, and `person`.
- **Bounding Boxes & Confidence**: All coordinates finite and valid; confidence scores bounded in $[0.0, 1.0]$.
- **Metadata Propagation**: `frame_id`, `camera_id`, and `timestamp` propagated with zero data loss.

## 11. Limitations & Notes
- This evaluation validates structural integration, schema compliance, and visual plausibility. It does not calculate mAP/F1 metrics due to lack of ground-truth annotations.

---

## Final Status Classifications

- **Fire/Smoke Model**: PASS
- **Person Model**: PASS
- **YOLOAdapter**: PASS

**Overall**: **READY FOR BACKEND INTEGRATION**
