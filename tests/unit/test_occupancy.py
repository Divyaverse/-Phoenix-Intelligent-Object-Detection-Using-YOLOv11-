"""
Unit tests for occupancy estimation and predictive blockage scoring.
"""

from datetime import datetime, timezone
import pytest

from app.decision.occupancy import ApproximateOccupancyEstimator
from app.decision.prediction import PredictiveBlockageEngine
from app.domain.enums import DetectionType, SmokeGrowthTrend
from app.domain.models import (
    BoundingBox,
    Detection,
    NavigationEdge,
    NavigationNode,
    Point2D,
    SmokeObservation,
)


def test_approximate_occupancy_estimation():
    """Verify person detections are correctly associated with closest navigation node."""
    estimator = ApproximateOccupancyEstimator()

    nodes = [
        NavigationNode(node_id="n_zone_A", building_id="bld_1", floor_id="fl_1", label="Zone A", x=2.0, y=2.0),
        NavigationNode(node_id="n_zone_B", building_id="bld_1", floor_id="fl_1", label="Zone B", x=20.0, y=2.0),
    ]

    # Two persons near Zone A, one person near Zone B
    persons = [
        Detection(
            frame_id="f1",
            camera_id="c1",
            class_name=DetectionType.PERSON,
            confidence=0.90,
            bbox=BoundingBox(x1=0, y1=0, x2=10, y2=10),
            floor_point=Point2D(x=2.2, y=2.1),
        ),
        Detection(
            frame_id="f1",
            camera_id="c1",
            class_name=DetectionType.PERSON,
            confidence=0.85,
            bbox=BoundingBox(x1=0, y1=0, x2=10, y2=10),
            floor_point=Point2D(x=1.8, y=2.4),
        ),
        Detection(
            frame_id="f1",
            camera_id="c1",
            class_name=DetectionType.PERSON,
            confidence=0.92,
            bbox=BoundingBox(x1=0, y1=0, x2=10, y2=10),
            floor_point=Point2D(x=19.5, y=2.0),
        ),
    ]

    occ_map = estimator.estimate_node_occupancies(nodes, persons)

    assert occ_map["n_zone_A"] == 2
    assert occ_map["n_zone_B"] == 1


def test_predictive_blockage_engine():
    """Verify predictive blockage scores correlate with temporal growth trends."""
    engine = PredictiveBlockageEngine()

    nodes = [
        NavigationNode(node_id="n1", building_id="bld_1", floor_id="fl_1", label="N1", x=0.0, y=0.0),
        NavigationNode(node_id="n2", building_id="bld_1", floor_id="fl_1", label="N2", x=10.0, y=0.0),
    ]
    edges = [
        NavigationEdge(
            edge_id="e_corridor",
            building_id="bld_1",
            floor_id="fl_1",
            from_node="n1",
            to_node="n2",
            length_meters=10.0,
            hazard_score=0.60,
        )
    ]
    nodes_dict = {n.node_id: n for n in nodes}

    obs_rapid = SmokeObservation(
        observation_id="obs_1",
        camera_id="cam_01",
        area_px2=4000.0,
        delta_area_px2=1500.0,
        dt_seconds=2.0,
        growth_rate_px2_per_sec=750.0,
        trend=SmokeGrowthTrend.RAPID_GROWTH,
        confidence=0.90,
    )

    blockage_map = engine.predict_blockage_scores(edges, nodes_dict, [obs_rapid])

    # Predicted blockage should be calculated and elevated
    assert blockage_map["e_corridor"] > 0.40
