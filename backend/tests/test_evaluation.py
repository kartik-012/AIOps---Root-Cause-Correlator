"""End-to-end evaluation benchmark verification suite (Gap #3 — Honest Benchmark Pipeline)."""

from app.engines.evaluation_runner import EvaluationRunner


def test_evaluation_stream_ingestion_and_real_latency_timing():
    """Verify EvaluationRunner streams raw telemetry through DetectionEngine -> CorrelationEngine
    with measured wall-clock latency timing and compares against a naive baseline.
    """
    runner = EvaluationRunner()
    report = runner.run_all()

    assert report.total_scenarios == 30
    assert report.detection_events_processed >= 3000
    assert report.top1_accuracy >= 0.80
    assert report.top1_accuracy > report.naive_baseline_accuracy
    assert report.mean_pipeline_latency_ms > 0.0
    assert report.p95_pipeline_latency_ms > 0.0
    assert report.suppression_tn == 30
    assert report.suppression_fp == 0
