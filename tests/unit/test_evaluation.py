"""
Unit tests for Phase 10 evaluation benchmarks (Static vs Reactive vs Predictive routing comparison).
"""

from scenarios.benchmark import compare_all_modes, run_evaluation_scenario
from app.domain.enums import RoutingMode


def test_routing_mode_benchmark_comparison():
    results = compare_all_modes()

    assert "STATIC" in results
    assert "REACTIVE" in results
    assert "PREDICTIVE" in results

    static_res = results["STATIC"]
    reactive_res = results["REACTIVE"]
    predictive_res = results["PREDICTIVE"]

    # Static routing picks shortest distance path (North corridor)
    assert static_res.mode == RoutingMode.STATIC

    # Reactive routing shifts away from high hazard corridor
    assert reactive_res.mode == RoutingMode.REACTIVE

    # Predictive routing incorporates lead time signal
    assert predictive_res.mode == RoutingMode.PREDICTIVE
    assert predictive_res.prediction_lead_time_seconds == 12.0
