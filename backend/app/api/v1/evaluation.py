"""Evaluation API router — Runs the full synthetic scenario test suite and returns live benchmark metrics."""

from fastapi import APIRouter
from app.engines.evaluation_runner import EvaluationRunner
from app.models.schemas import EvaluationMetrics

router = APIRouter()


@router.post("/eval/run-scenarios", response_model=EvaluationMetrics)
def run_evaluation_scenarios():
    """Run all 30 ground-truth injected scenarios through the real engines and return computed metrics."""
    runner = EvaluationRunner()
    report = runner.run_all()

    return EvaluationMetrics(
        top1_accuracy=report.top1_accuracy,
        top3_accuracy=report.top3_accuracy,
        multi_incident_separation_accuracy=report.multi_incident_separation_accuracy,
        suppression_precision=report.suppression_precision,
        suppression_recall=report.suppression_recall,
        blast_radius_accuracy=report.blast_radius_accuracy,
        mean_detection_time_seconds=report.mean_detection_time_seconds,
        total_scenarios=report.total_scenarios,
        passed=report.passed_scenarios,
        failed=report.failed_scenarios,
    )
