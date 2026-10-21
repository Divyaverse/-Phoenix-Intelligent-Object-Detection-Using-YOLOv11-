"""
YOLOv11 perception adapter and structured detection processor.
"""

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
import numpy as np

from app.core.config import PerceptionConfig, settings
from app.core.errors import ModelUnavailableError
from app.domain.enums import DetectionType
from app.domain.interfaces import Detector
from app.domain.models import BoundingBox, Detection, Point2D


class YOLOAdapter(Detector):
    """
    Ultralytics YOLO dual-model perception adapter converting raw tensor predictions
    from fire/smoke and person models into structured Detection domain models.
    """

    CLASS_NAME_MAP = {
        "fire": DetectionType.FIRE,
        "smoke": DetectionType.SMOKE,
        "person": DetectionType.PERSON,
        "people": DetectionType.PERSON,
        "human": DetectionType.PERSON,
    }

    def __init__(
        self,
        model_path: Optional[str] = None,
        fire_smoke_model_path: Optional[str] = None,
        person_model_path: Optional[str] = None,
        config: Optional[PerceptionConfig] = None,
        device: Optional[str] = None,
    ) -> None:
        self.config = config or settings.perception
        # Support legacy model_path kwarg or dedicated model paths
        self.fire_smoke_model_path = fire_smoke_model_path or model_path or getattr(self.config, "fire_smoke_model_path", None) or self.config.model_path
        self.person_model_path = person_model_path or getattr(self.config, "person_model_path", None) or "models/yolo11n.pt"
        self.device = device or self.config.device
        
        self._fire_smoke_model: Any = None
        self._person_model: Any = None
        self._fire_smoke_class_names: dict[int, str] = {}
        self._person_class_names: dict[int, str] = {}
        self._load_models()

    def _load_single_model(self, model_path_str: str) -> tuple[Any, dict[int, str]]:
        model_file = Path(model_path_str)
        if not model_file.is_file():
            raise ModelUnavailableError(
                f"YOLO model file not found at: {model_path_str}",
                details={"model_path": model_path_str},
            )

        try:
            from ultralytics import YOLO
            model = YOLO(str(model_file))
            class_names: dict[int, str] = {}
            if hasattr(model, "names") and isinstance(model.names, dict):
                class_names = model.names
            elif hasattr(model, "model") and hasattr(model.model, "names"):
                class_names = model.model.names
            return model, class_names
        except Exception as e:
            raise ModelUnavailableError(
                f"Failed to load YOLO model at {model_path_str}: {str(e)}",
                details={"model_path": model_path_str, "error": str(e)},
            )

    def _load_models(self) -> None:
        """Load both fire/smoke and person YOLO model weights from local files."""
        self._fire_smoke_model, self._fire_smoke_class_names = self._load_single_model(self.fire_smoke_model_path)
        self._person_model, self._person_class_names = self._load_single_model(self.person_model_path)

    @property
    def model_path(self) -> str:
        """Backward-compatible property returning primary model path."""
        return self.fire_smoke_model_path

    def is_ready(self) -> bool:
        return self._fire_smoke_model is not None and self._person_model is not None

    def get_supported_classes(self) -> list[str]:
        return self.config.supported_classes

    def detect(
        self,
        frame: np.ndarray,
        frame_id: str,
        camera_id: str,
        timestamp_seconds: float,
    ) -> list[Detection]:
        """
        Run inference on frame with both fire/smoke and person models,
        returning structured, confidence-filtered unified detections.
        """
        if not self.is_ready():
            raise ModelUnavailableError("Perception models are not loaded or ready.")

        timestamp = datetime.fromtimestamp(timestamp_seconds, tz=timezone.utc)
        detections: list[Detection] = []

        # Model configs to iterate over: (model, class_names, target_types)
        model_runs = [
            (self._fire_smoke_model, self._fire_smoke_class_names, {DetectionType.FIRE, DetectionType.SMOKE}),
            (self._person_model, self._person_class_names, {DetectionType.PERSON}),
        ]

        det_index = 0
        for model, class_names, target_types in model_runs:
            results = model.predict(
                source=frame,
                device=self.device,
                verbose=False,
                imgsz=self.config.input_resolution[0],
            )

            if not results:
                continue

            result = results[0]
            if result.boxes is None or len(result.boxes) == 0:
                continue

            boxes = result.boxes.xyxy.cpu().numpy()
            confidences = result.boxes.conf.cpu().numpy()
            class_ids = result.boxes.cls.cpu().numpy().astype(int)

            for i in range(len(boxes)):
                cls_id = class_ids[i]
                conf = float(confidences[i])
                raw_cls_name = class_names.get(cls_id, "").lower().strip()

                # Map raw class name to domain DetectionType
                detection_type = self.CLASS_NAME_MAP.get(raw_cls_name)
                if detection_type is None or detection_type not in target_types:
                    # Class not target for this specific model run
                    continue

                # Confidence filtering per class
                min_conf = self.config.confidence_thresholds.get(detection_type.value, 0.30)
                if conf < min_conf:
                    continue

                x1, y1, x2, y2 = float(boxes[i][0]), float(boxes[i][1]), float(boxes[i][2]), float(boxes[i][3])
                bbox = BoundingBox(x1=x1, y1=y1, x2=x2, y2=y2)

                detections.append(
                    Detection(
                        detection_id=f"det_{camera_id}_{frame_id}_{det_index}",
                        frame_id=frame_id,
                        timestamp=timestamp,
                        camera_id=camera_id,
                        class_name=detection_type,
                        confidence=conf,
                        bbox=bbox,
                    )
                )
                det_index += 1

        return detections


class MockDetector(Detector):
    """
    Mock detector for automated test suites and synthetic verification.
    """

    def __init__(self, predefined_detections: Optional[list[Detection]] = None) -> None:
        self.predefined_detections = predefined_detections or []
        self._ready = True

    def is_ready(self) -> bool:
        return self._ready

    def set_ready(self, ready: bool) -> None:
        self._ready = ready

    def get_supported_classes(self) -> list[str]:
        return ["fire", "smoke", "person"]

    def detect(
        self,
        frame: np.ndarray,
        frame_id: str,
        camera_id: str,
        timestamp_seconds: float,
    ) -> list[Detection]:
        if not self._ready:
            raise ModelUnavailableError("Mock detector is set to unavailable state")
        return [det for det in self.predefined_detections if det.camera_id == camera_id or not det.camera_id]
