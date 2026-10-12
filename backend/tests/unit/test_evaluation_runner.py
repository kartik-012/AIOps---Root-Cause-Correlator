"""Unit tests for EvaluationRunner — End-to-End Streaming Evaluation Harness with Wilson 95% Confidence Intervals."""

from app.engines.evaluation_runner import EvaluationRunner, compute_wilson_ci_95
from app.api.v1.evaluation import run_evaluation_scenarios


def test_wilson_confidence_interval_95_finite_sample_properties():
    """Differentiator #10: Verify Wilson score 95% CI avoids degenerate [1.0, 1.0] on finite N."""
    # For 16/16 successes, Wald CI is [1.0, 1.0], whereas Wilson 95% CI has lower bound ~0.8064
    low_16, high_16 = compute_wilson_ci_95(16, 16)
    assert 0.80 <= low_16 < 0.82
    assert high_16 == 1.0

    # For 30/30 successes, lower bound is ~0.8865
    low_30, high_30 = compute_wilson_ci_95(30, 30)
    assert 0.88 <= low_30 < 0.90
    assert high_30 == 1.0
    assert low_30 > low_16

    # Edge case n=0
    assert compute_wilson_ci_95(0, 0) == (0.0, 0.0)


def test_end_to_end_streaming_evaluation_runner_with_confidence_intervals():
    """Differentiator #10: Verify full 30-scenario streaming evaluation pipeline, Wilson 95% CIs, and latency percentiles."""
    runner = EvaluationRunner()
    report = runner.run_all()

    assert report.total_scenarios == 30
    assert report.passed_scenarios == 30
    assert report.failed_scenarios == 0
    assert report.top1_accuracy == 1.0
    assert report.top3_accuracy == 1.0
    assert report.multi_incident_separation_accuracy == 1.0
    assert report.suppression_precision == 1.0
    assert report.suppression_recall == 1.0
    assert report.suppression_f1 == 1.0
    assert report.blast_radius_accuracy == 1.0

    # Verify non-degenerate Wilson 95% CIs
    assert 0.78 <= report.top1_confidence_interval_95[0] < 0.90
    assert report.top1_confidence_interval_95[1] == 1.0
    assert 0.88 <= report.overall_pass_confidence_interval_95[0] < 0.90
    assert report.overall_pass_confidence_interval_95[1] == 1.0

    # Verify streaming event count and latency percentiles
    assert report.detection_events_processed >= 300
    assert report.p50_pipeline_latency_ms > 0.0
    assert report.p95_pipeline_latency_ms >= report.p50_pipeline_latency_ms


def test_evaluation_api_endpoint_returns_confidence_intervals():
    """Differentiator #10: Verify run_evaluation_scenarios exposes Wilson 95% CIs and p50/p95 latencies."""
    metrics = run_evaluation_scenarios()
    assert metrics.total_scenarios == 30
    assert metrics.passed == 30
    assert len(metrics.top1_confidence_interval_95) == 2
    assert len(metrics.overall_pass_confidence_interval_95) == 2
    assert metrics.suppression_f1 == 1.0
    assert metrics.p50_pipeline_latency_ms is not None
    assert metrics.p95_pipeline_latency_ms is not None
