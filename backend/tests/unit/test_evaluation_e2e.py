"""Step 10 Item 1 & 2: End-to-End Evaluation Test Suite & 100-Node Graph Benchmark.

Verifies:
1. Full 30-scenario pipeline execution through DetectionEngine -> CorrelationEngine.
2. Top-1 and Top-3 accuracy with Wilson 95% confidence intervals against naive baseline.
3. Multi-incident separation of simultaneous cascading failures.
4. Wall-clock sub-second p50/p95/p99 processing latency on a 100-node microservice graph.
"""

import pytest
from app.engines.evaluation_runner import EvaluationRunner


def test_e2e_evaluation_accuracy_and_naive_baseline_comparison():
    runner = EvaluationRunner()
    report = runner.run_all()

    # Verify scenario coverage
    assert report.total_scenarios == 30
    assert report.passed_scenarios >= 28, f"Expected at least 28/30 passed, got {report.passed_scenarios}"
    assert report.failed_scenarios <= 2

    # Verify Top-1 and Top-3 accuracy claims
    assert report.top1_accuracy >= 0.90, f"Top-1 accuracy {report.top1_accuracy} below 0.90 target"
    assert report.top3_accuracy >= 0.95, f"Top-3 accuracy {report.top3_accuracy} below 0.95 target"
    assert report.multi_incident_separation_accuracy == 1.0

    # Verify Wilson 95% confidence intervals
    assert len(report.top1_confidence_interval_95) == 2
    ci_lower, ci_upper = report.top1_confidence_interval_95
    assert 0.70 <= ci_lower <= ci_upper <= 1.0

    # Verify real telemetry was processed through DetectionEngine
    assert report.detection_events_processed > 100, (
        f"Expected real detector ingestion (>100 samples), got {report.detection_events_processed}"
    )

    # Verify naive non-topological baseline suffers lower or equal accuracy compared to topological RCA
    assert report.naive_baseline_accuracy <= report.top1_accuracy


def test_100_node_graph_latency_benchmark_subsecond():
    """Verify sub-second p50, p95, and p99 correlation compute latency on a 100-node microservice graph."""
    benchmark = EvaluationRunner.benchmark_100_node_graph_latency(iterations=30)

    assert benchmark["nodes"] == 100
    assert benchmark["edges"] >= 80
    assert benchmark["iterations"] == 30

    # Assert sub-second wall-clock compute requirements
    assert benchmark["p50_ms"] < 100.0, f"p50 latency {benchmark['p50_ms']}ms exceeded 100ms budget"
    assert benchmark["p95_ms"] < 250.0, f"p95 latency {benchmark['p95_ms']}ms exceeded 250ms budget"
    assert benchmark["p99_ms"] < 500.0, f"p99 latency {benchmark['p99_ms']}ms exceeded 500ms budget"
