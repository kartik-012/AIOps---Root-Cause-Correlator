"""Automated benchmark test suite executing all 30 ground-truth failure scenarios."""

from app.engines.evaluation_runner import EvaluationRunner


def test_full_synthetic_evaluation_suite(capsys):
    runner = EvaluationRunner()
    report = runner.run_all()

    # Print evaluation metrics report
    print("\n" + "=" * 70)
    print("      AIOps ROOT CAUSE CORRELATOR — BENCHMARK EVALUATION REPORT")
    print("=" * 70)
    print(f"Total Scenarios Evaluated          : {report.total_scenarios}")
    print(f"Passed Scenarios                   : {report.passed_scenarios}")
    print(f"Failed Scenarios                   : {report.failed_scenarios}")
    print(f"EWMA Telemetry Samples Processed   : {report.detection_events_processed}")
    print("-" * 70)
    print(f"Top-1 Accuracy (Graph Correlator)  : {report.top1_accuracy * 100:.1f}%")
    print(f"Top-1 Accuracy (Naive Z Baseline)  : {report.naive_baseline_accuracy * 100:.1f}%")
    print(f"Top-3 Accuracy                     : {report.top3_accuracy * 100:.1f}%")
    print(f"Multi-Incident Separation Accuracy : {report.multi_incident_separation_accuracy * 100:.1f}%")
    print(f"Suppression Precision              : {report.suppression_precision * 100:.1f}%")
    print(f"Suppression Recall                 : {report.suppression_recall * 100:.1f}%")
    print(
        f"Suppression Confusion Matrix       : "
        f"TP={report.suppression_tp}, TN={report.suppression_tn}, "
        f"FP={report.suppression_fp}, FN={report.suppression_fn}"
    )
    print(f"Blast Radius Accuracy              : {report.blast_radius_accuracy * 100:.1f}%")
    print(f"Mean Pipeline Latency (ms)         : {report.mean_pipeline_latency_ms:.3f}ms")
    print(f"p95 Pipeline Latency (ms)          : {report.p95_pipeline_latency_ms:.3f}ms")
    print("=" * 70)

    # Detailed per-scenario log
    print("\nScenario Breakdown:")
    for d in report.details:
        status_icon = "PASS" if d["passed"] else "FAIL"
        print(f"  [{status_icon}] Scenario #{d['scenario_id']:02d} ({d['category']}) - {d['name']}: {d['message']}")
    print("=" * 70 + "\n")

    # Assert rigorous benchmarks and anti-rigging invariants
    assert report.total_scenarios == 30
    assert report.detection_events_processed > 2000, "DetectionEngine must actively process EWMA burn-in and fault streams"
    assert report.top1_accuracy >= 0.80, f"Expected top1_accuracy >= 80%, got {report.top1_accuracy * 100}%"
    assert report.top1_accuracy > report.naive_baseline_accuracy, (
        "Graph correlation must measurably outperform naive non-topological z-score alerting"
    )
    assert report.multi_incident_separation_accuracy >= 0.70
    assert report.suppression_recall >= 0.80
    assert report.suppression_tn >= 20, "Real incidents must be evaluated against SuppressionEngine to prove low false-positive suppression"
    assert report.suppression_fp == 0, "Real production incidents must not be suppressed by benign templates"
