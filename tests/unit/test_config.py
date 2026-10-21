"""
Unit tests for configuration loading and validation.
"""

from app.core.config import Settings, load_settings


def test_default_settings_instantiation():
    """Verify settings defaults are populated correctly."""
    settings = Settings()
    assert settings.project_name == "PHOENIX"
    assert settings.perception.model_path == "models/yolo11n.pt"
    assert settings.routing.weights["hazard_weight"] == 0.40
    assert settings.eta.base_walking_speed_mps == 1.20
    assert settings.freshness_threshold_seconds == 5.0


def test_load_settings_from_yaml():
    """Verify loading settings from default.yaml succeeds."""
    settings = load_settings("configs/default.yaml")
    assert settings.project_name == "PHOENIX"
    assert "fire" in settings.perception.confidence_thresholds
    assert settings.temporal.growth_rate_rapid_threshold_px2_per_sec == 250.0
    assert settings.risk.blocked_threshold == 0.85
