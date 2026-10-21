"""
Configuration management for PHOENIX using Pydantic Settings and YAML fallback.
"""

from pathlib import Path
from typing import Any, Optional
import yaml
from pydantic import BaseModel, Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class PerceptionConfig(BaseModel):
    model_path: str = "models/yolo11n.pt"
    device: str = "cpu"
    confidence_thresholds: dict[str, float] = Field(
        default_factory=lambda: {"fire": 0.35, "smoke": 0.30, "person": 0.40}
    )
    supported_classes: list[str] = Field(
        default_factory=lambda: ["fire", "smoke", "person"]
    )
    input_resolution: list[int] = Field(default_factory=lambda: [640, 640])
    max_fps: float = 15.0
    video_source_path: str = "videos/Main_video.mp4"
    primary_camera_id: str = "CAM-MAIN-01"


class TemporalConfig(BaseModel):
    history_window_seconds: float = 10.0
    min_observations_for_trend: int = 3
    growth_rate_rapid_threshold_px2_per_sec: float = 250.0
    growth_rate_moderate_threshold_px2_per_sec: float = 50.0
    noise_area_filter_px2: float = 25.0
    smoothing_factor_alpha: float = 0.3


class SpatialConfig(BaseModel):
    default_coordinate_unit: str = "meters"
    grid_resolution_meters: float = 0.5
    min_calibration_points: int = 4
    reprojection_error_threshold: float = 15.0


class RiskConfig(BaseModel):
    base_hazard_weights: dict[str, float] = Field(
        default_factory=lambda: {"fire": 1.00, "smoke": 0.60}
    )
    growth_risk_multiplier: float = 1.50
    proximity_decay_lambda: float = 0.50
    levels: dict[str, float] = Field(
        default_factory=lambda: {
            "low_max": 0.25,
            "medium_max": 0.50,
            "high_max": 0.75,
            "critical_threshold": 0.75,
        }
    )
    blocked_threshold: float = 0.85


class OccupancyConfig(BaseModel):
    congestion_factor_weight: float = 0.30
    max_capacity_per_corridor_sqm: float = 1.5


class PredictionConfig(BaseModel):
    blockage_prediction_horizon_seconds: float = 30.0
    growth_extrapolation_weight: float = 0.70
    proximity_hazard_weight: float = 0.30
    high_risk_blockage_threshold: float = 0.70


class RoutingConfig(BaseModel):
    algorithm: str = "dijkstra"
    weights: dict[str, float] = Field(
        default_factory=lambda: {
            "distance_weight": 0.35,
            "hazard_weight": 0.40,
            "occupancy_weight": 0.10,
            "predicted_blockage_weight": 0.15,
        }
    )
    hard_block_hazard_threshold: float = 0.90
    allow_degraded_routing: bool = True


class ETAConfig(BaseModel):
    base_walking_speed_mps: float = 1.20
    stairs_speed_factor: float = 0.60
    congestion_slowdown_max_factor: float = 0.50
    smoke_visibility_slowdown_factor: float = 0.70


class Settings(BaseSettings):
    """Global system configuration for PHOENIX."""

    project_name: str = "PHOENIX"
    env: str = "development"
    debug: bool = True
    api_v1_str: str = "/api/v1"

    @property
    def api_v1_prefix(self) -> str:
        return self.api_v1_str

    @property
    def environment(self) -> str:
        return self.env

    @property
    def DATABASE_URL(self) -> str:
        return self.database_url

    host: str = "0.0.0.0"
    port: int = 8000
    frontend_port: int = 3000

    jwt_secret_key: str = "phoenix-prototype-secret-key-change-in-production-never-hardcode"
    jwt_algorithm: str = "HS256"
    access_token_expire_minutes: int = 480
    refresh_token_expire_days: int = 7

    database_url: str = "sqlite:///./phoenix.db"
    freshness_threshold_seconds: float = 5.0

    perception: PerceptionConfig = Field(default_factory=PerceptionConfig)
    temporal: TemporalConfig = Field(default_factory=TemporalConfig)
    spatial: SpatialConfig = Field(default_factory=SpatialConfig)
    risk: RiskConfig = Field(default_factory=RiskConfig)
    occupancy: OccupancyConfig = Field(default_factory=OccupancyConfig)
    prediction: PredictionConfig = Field(default_factory=PredictionConfig)
    routing: RoutingConfig = Field(default_factory=RoutingConfig)
    eta: ETAConfig = Field(default_factory=ETAConfig)

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


def load_settings(config_yaml_path: Optional[str] = None) -> Settings:
    """
    Load settings optionally overriding defaults with a YAML configuration file.
    """
    yaml_data: dict[str, Any] = {}
    path = Path(config_yaml_path or "configs/default.yaml")
    if path.is_file():
        try:
            with open(path, "r", encoding="utf-8") as f:
                content = yaml.safe_load(f)
                if isinstance(content, dict):
                    yaml_data = content
        except Exception:
            pass

    # Extract nested sections if present in YAML
    init_kwargs: dict[str, Any] = {}
    if "perception" in yaml_data:
        init_kwargs["perception"] = PerceptionConfig(**yaml_data["perception"])
    if "temporal" in yaml_data:
        init_kwargs["temporal"] = TemporalConfig(**yaml_data["temporal"])
    if "spatial" in yaml_data:
        init_kwargs["spatial"] = SpatialConfig(**yaml_data["spatial"])
    if "risk" in yaml_data:
        init_kwargs["risk"] = RiskConfig(**yaml_data["risk"])
    if "occupancy" in yaml_data:
        init_kwargs["occupancy"] = OccupancyConfig(**yaml_data["occupancy"])
    if "prediction" in yaml_data:
        init_kwargs["prediction"] = PredictionConfig(**yaml_data["prediction"])
    if "routing" in yaml_data:
        init_kwargs["routing"] = RoutingConfig(**yaml_data["routing"])
    if "eta" in yaml_data:
        init_kwargs["eta"] = ETAConfig(**yaml_data["eta"])

    if "system" in yaml_data and isinstance(yaml_data["system"], dict):
        sys_cfg = yaml_data["system"]
        if "name" in sys_cfg:
            init_kwargs["project_name"] = sys_cfg["name"]
        if "environment" in sys_cfg:
            init_kwargs["env"] = sys_cfg["environment"]
        if "freshness_threshold_seconds" in sys_cfg:
            init_kwargs["freshness_threshold_seconds"] = float(sys_cfg["freshness_threshold_seconds"])

    return Settings(**init_kwargs)


# Global settings singleton instance
settings = load_settings()
