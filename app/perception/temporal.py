"""
Temporal smoke observation tracker and growth rate analyzer.
"""

from collections import deque
from datetime import datetime, timezone
from typing import Optional
import uuid

from app.core.config import TemporalConfig, settings
from app.domain.enums import DetectionType, SmokeGrowthTrend
from app.domain.interfaces import TemporalAnalyzer
from app.domain.models import Detection, SmokeObservation


class FrameSmokeRecord:
    """Internal historical record of smoke observation at a given timestamp."""

    def __init__(self, timestamp: float, area_px2: float, confidence: float) -> None:
        self.timestamp = timestamp
        self.area_px2 = area_px2
        self.confidence = confidence


class TemporalSmokeAnalyzer(TemporalAnalyzer):
    """
    Tracks observed smoke area over time to compute the smoke-region growth rate (Δarea / Δt).
    Explicitly labeled as 2D observed image area growth, not physical 3D smoke velocity.
    """

    def __init__(self, config: Optional[TemporalConfig] = None) -> None:
        self.config = config or settings.temporal
        # History queue per camera_id: deque[FrameSmokeRecord]
        self._history: dict[str, deque[FrameSmokeRecord]] = {}
        # Exponential moving average of growth rate per camera
        self._smoothed_rates: dict[str, float] = {}

    def process_observations(
        self,
        camera_id: str,
        detections: list[Detection],
        timestamp_seconds: float,
    ) -> Optional[SmokeObservation]:
        """
        Ingest current frame detections, calculate smoke-region growth rate and classify trend.
        """
        if camera_id not in self._history:
            self._history[camera_id] = deque()
            self._smoothed_rates[camera_id] = 0.0

        history = self._history[camera_id]

        # Extract and sum smoke detection areas for current frame
        smoke_detections = [d for d in detections if d.class_name == DetectionType.SMOKE]

        if not smoke_detections:
            # If no smoke detected in current frame, clean old records and decay rate
            self._prune_history(camera_id, timestamp_seconds)
            self._smoothed_rates[camera_id] *= 0.5
            return None

        current_area = sum(d.bbox.area for d in smoke_detections)
        avg_confidence = sum(d.confidence for d in smoke_detections) / len(smoke_detections)

        # Apply noise floor filtering
        if current_area < self.config.noise_area_filter_px2:
            return None

        # Check for duplicate frames (same timestamp as last record)
        if history and abs(timestamp_seconds - history[-1].timestamp) < 1e-4:
            # Duplicate timestamp; replace latest record
            history[-1] = FrameSmokeRecord(timestamp_seconds, current_area, avg_confidence)
        else:
            history.append(FrameSmokeRecord(timestamp_seconds, current_area, avg_confidence))

        # Prune records outside the sliding time window
        self._prune_history(camera_id, timestamp_seconds)

        # If insufficient history for trend computation, return baseline observation
        if len(history) < 2:
            return SmokeObservation(
                observation_id=f"obs_{uuid.uuid4().hex[:8]}",
                camera_id=camera_id,
                timestamp=datetime.fromtimestamp(timestamp_seconds, tz=timezone.utc),
                area_px2=current_area,
                delta_area_px2=0.0,
                dt_seconds=0.0,
                growth_rate_px2_per_sec=0.0,
                smoothed_growth_rate=0.0,
                trend=SmokeGrowthTrend.UNKNOWN,
                confidence=avg_confidence,
            )

        # Calculate growth rate between oldest available record in window and current record
        earliest = history[0]
        latest = history[-1]

        dt = latest.timestamp - earliest.timestamp
        if dt <= 1e-3:
            growth_rate = 0.0
            delta_area = 0.0
        else:
            delta_area = latest.area_px2 - earliest.area_px2
            growth_rate = delta_area / dt

        # Apply Exponential Moving Average smoothing
        alpha = self.config.smoothing_factor_alpha
        prev_smoothed = self._smoothed_rates.get(camera_id, growth_rate)
        smoothed_rate = alpha * growth_rate + (1.0 - alpha) * prev_smoothed
        self._smoothed_rates[camera_id] = smoothed_rate

        # Classify trend based on configurable thresholds
        trend = self._classify_trend(smoothed_rate)

        return SmokeObservation(
            observation_id=f"obs_{uuid.uuid4().hex[:8]}",
            camera_id=camera_id,
            timestamp=datetime.fromtimestamp(timestamp_seconds, tz=timezone.utc),
            area_px2=latest.area_px2,
            delta_area_px2=delta_area,
            dt_seconds=dt,
            growth_rate_px2_per_sec=round(growth_rate, 2),
            smoothed_growth_rate=round(smoothed_rate, 2),
            trend=trend,
            confidence=round(avg_confidence, 3),
        )

    def _prune_history(self, camera_id: str, current_timestamp: float) -> None:
        """Remove observations older than history_window_seconds."""
        history = self._history.get(camera_id)
        if not history:
            return

        cutoff = current_timestamp - self.config.history_window_seconds
        while history and history[0].timestamp < cutoff:
            history.popleft()

    def _classify_trend(self, growth_rate: float) -> SmokeGrowthTrend:
        """Classify temporal growth trend based on configured experimental thresholds."""
        if growth_rate >= self.config.growth_rate_rapid_threshold_px2_per_sec:
            return SmokeGrowthTrend.RAPID_GROWTH
        elif growth_rate >= self.config.growth_rate_moderate_threshold_px2_per_sec:
            return SmokeGrowthTrend.MODERATE_GROWTH
        elif growth_rate <= -self.config.growth_rate_moderate_threshold_px2_per_sec:
            return SmokeGrowthTrend.DECREASING
        else:
            return SmokeGrowthTrend.STABLE

    def reset_camera_history(self, camera_id: str) -> None:
        """Reset history buffer for a given camera."""
        if camera_id in self._history:
            self._history[camera_id].clear()
            self._smoothed_rates[camera_id] = 0.0
