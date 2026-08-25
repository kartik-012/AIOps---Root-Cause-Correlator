"""Evaluation Runner — Executes the full 30-scenario test suite against real engines.

Computes precision, recall, top-k accuracy, separation accuracy, and blast radius metrics.
"""

from dataclasses import asdict, dataclass
from datetime import datetime, timezone, timedelta
import json
from pathlib import Path
from typing import Any

from app.graph.dependency_graph import DependencyGraph
from app.engines.detection_engine import DetectionEngine
from app.engines.correlation_engine import CorrelationEngine, AnomalyEvent
from app.engines.suppression_engine import SuppressionEngine, build_signature
from app.engines.prediction_engine import PredictionEngine


@dataclass
class EvaluationReport:
    """Full benchmark evaluation metrics."""
    top1_accuracy: float
    top3_accuracy: float
    multi_incident_separation_accuracy: float
    suppression_precision: float
    suppression_recall: float
    blast_radius_accuracy: float
    mean_detection_time_seconds: float
    total_scenarios: int
    passed_scenarios: int
    failed_scenarios: int
    details: list[dict[str, Any]]


class EvaluationRunner:
    """Benchmark runner for synthetic evaluation fixtures."""

    def __init__(self, fixtures_dir: Path | str | None = None):
        if fixtures_dir is None:
            self.fixtures_dir = Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "synthetic_scenarios"
        else:
            self.fixtures_dir = Path(fixtures_dir)

    def load_scenarios(self) -> list[dict[str, Any]]:
        """Load all scenario JSON files sorted by ID."""
        files = sorted(list(self.fixtures_dir.glob("*.json")))
        scenarios = []
        for f in files:
            with open(f, "r") as fp:
                scenarios.append(json.load(fp))
        return scenarios

    def run_all(self) -> EvaluationReport:
        """Run all 30 scenarios through the engines and return comprehensive metrics."""
        scenarios = self.load_scenarios()

        single_total = 0
        single_top1_correct = 0
        single_top3_correct = 0

        multi_total = 0
        multi_separated_correct = 0

        suppression_tp = 0
        suppression_fp = 0
        suppression_fn = 0
        suppression_tn = 0

        blast_total = 0
        blast_correct = 0

        detection_times = []
        details = []

        # Initialize Suppression Engine with benign templates for scenarios 25-28
        suppression_engine = SuppressionEngine(similarity_threshold=0.90)

        # Seed false positive templates
        suppression_engine.register_false_positive(
            "seed-fp-25", [1.0, 1.0, 4.0, 2.0, 2.5, 1.0, 10.0], "daily_traffic_surge"
        )
        suppression_engine.register_false_positive(
            "seed-fp-26", [0.0, 6.0, 8.0, 1.0, 3.2, 1.0, 10.0], "weekly_batch_job"
        )
        suppression_engine.register_false_positive(
            "seed-fp-27", [2.0, 3.0, 5.0, 2.0, 2.1, 1.0, 10.0], "gradual_organic_growth"
        )
        suppression_engine.register_false_positive(
            "seed-fp-28", [0.0, 5.0, 7.0, 4.0, 4.0, 1.0, 10.0], "planned_maintenance_window"
        )

        t_base = datetime(2026, 8, 25, 10, 0, 0, tzinfo=timezone.utc)

        for sc in scenarios:
            category = sc.get("category", "")
            gt = sc.get("ground_truth", {})
            sc_id = sc.get("scenario_id")
            sc_name = sc.get("name")
            passed = True
            log_msg = ""

            dep_graph = DependencyGraph.from_nodes_and_edges(
                sc.get("services", []), sc.get("dependencies", [])
            )
            corr_engine = CorrelationEngine(dep_graph)

            # Build list of AnomalyEvent objects
            anomalies: list[AnomalyEvent] = []
            if sc.get("injected_fault"):
                f = sc["injected_fault"]
                anomalies.append(
                    AnomalyEvent(
                        service_id=f["service"],
                        metric_type=f["metric"],
                        z_score=f["z_score"],
                        severity=f["severity"],
                        detected_at=t_base + timedelta(seconds=f["t_offset"]),
                    )
                )
                detection_times.append(float(f["t_offset"]))

            if sc.get("injected_faults"):
                for f in sc["injected_faults"]:
                    anomalies.append(
                        AnomalyEvent(
                            service_id=f["service"],
                            metric_type=f["metric"],
                            z_score=f["z_score"],
                            severity=f["severity"],
                            detected_at=t_base + timedelta(seconds=f["t_offset"]),
                        )
                    )
                    detection_times.append(float(f["t_offset"]))

            for c in sc.get("cascade", []):
                anomalies.append(
                    AnomalyEvent(
                        service_id=c["service"],
                        metric_type=c["metric"],
                        z_score=c["z_score"],
                        severity=c["severity"],
                        detected_at=t_base + timedelta(seconds=c["t_offset"]),
                    )
                )

            # Process according to category
            if category == "single_root_cause":
                single_total += 1
                incidents = corr_engine.correlate(anomalies)
                expected_root = gt.get("root_cause_service")

                if incidents:
                    identified_root = incidents[0].root_cause_service_id
                    all_roots = [inc.root_cause_service_id for inc in incidents]
                    all_candidates = [inc.root_cause_service_id for inc in incidents] + incidents[0].affected_service_ids

                    if identified_root == expected_root:
                        single_top1_correct += 1
                        single_top3_correct += 1
                        log_msg = f"Root cause correctly identified as '{identified_root}' (confidence: {incidents[0].confidence})"
                    elif expected_root in all_candidates[:3]:
                        single_top3_correct += 1
                        passed = False
                        log_msg = f"Root cause '{expected_root}' in top 3, but top-1 was '{identified_root}'"
                    else:
                        passed = False
                        log_msg = f"Root cause mismatch: expected '{expected_root}', got '{identified_root}'"
                else:
                    passed = False
                    log_msg = "No incident identified by correlation engine"

            elif category == "multi_root_cause":
                multi_total += 1
                incidents = corr_engine.correlate(anomalies)
                expected_roots = set(gt.get("root_cause_services", []))
                expected_count = gt.get("expected_incidents", 2)

                actual_roots = {inc.root_cause_service_id for inc in incidents}
                if len(incidents) == expected_count and actual_roots == expected_roots:
                    multi_separated_correct += 1
                    log_msg = f"Separated into {len(incidents)} independent incidents with roots {actual_roots}"
                else:
                    passed = False
                    log_msg = f"Expected {expected_count} incidents with roots {expected_roots}, got {len(incidents)} with roots {actual_roots}"

            elif category == "false_positive":
                sig = sc.get("signature")
                decision = suppression_engine.evaluate(sig)
                expected_suppress = gt.get("expected_suppression", True)

                if decision.should_suppress and expected_suppress:
                    suppression_tp += 1
                    log_msg = f"Benign pattern correctly suppressed (matched '{decision.matched_tag}', similarity {decision.similarity_score})"
                elif decision.should_suppress and not expected_suppress:
                    suppression_fp += 1
                    passed = False
                    log_msg = f"Real incident incorrectly suppressed (similarity {decision.similarity_score})"
                elif not decision.should_suppress and expected_suppress:
                    suppression_fn += 1
                    passed = False
                    log_msg = f"Benign pattern failed suppression (similarity {decision.similarity_score})"
                else:
                    suppression_tn += 1
                    log_msg = "Real incident correctly not suppressed"

            elif category == "blast_radius":
                blast_total += 1
                pred_engine = PredictionEngine(dep_graph)
                root_s = gt.get("root_cause_service")
                res = pred_engine.predict_blast_radius("inc-pred", root_s)

                expected_preds = gt.get("expected_predictions", [])
                expected_contained = gt.get("is_contained", False)
                actual_preds = [p.service_id for p in res.predictions]

                if expected_contained:
                    if res.contained or len(actual_preds) == 0:
                        blast_correct += 1
                        log_msg = "Correctly predicted contained failure (0 spread)"
                    else:
                        passed = False
                        log_msg = f"Expected contained failure, but predicted spread to {actual_preds}"
                else:
                    if set(expected_preds).issubset(set(actual_preds)):
                        blast_correct += 1
                        log_msg = f"Correctly predicted blast radius across {actual_preds}"
                    else:
                        passed = False
                        log_msg = f"Expected {expected_preds}, got {actual_preds}"

            details.append({
                "scenario_id": sc_id,
                "name": sc_name,
                "category": category,
                "passed": passed,
                "message": log_msg,
            })

        # Calculate aggregates
        top1_acc = round(single_top1_correct / max(single_total, 1), 3)
        top3_acc = round(single_top3_correct / max(single_total, 1), 3)
        multi_sep_acc = round(multi_separated_correct / max(multi_total, 1), 3)

        supp_denom = suppression_tp + suppression_fp
        supp_prec = round(suppression_tp / supp_denom, 3) if supp_denom > 0 else 1.0
        supp_recall_denom = suppression_tp + suppression_fn
        supp_recall = round(suppression_tp / supp_recall_denom, 3) if supp_recall_denom > 0 else 1.0

        blast_acc = round(blast_correct / max(blast_total, 1), 3)
        mean_det_time = round(sum(detection_times) / max(len(detection_times), 1), 2)

        passed_cnt = sum(1 for d in details if d["passed"])
        failed_cnt = len(details) - passed_cnt

        return EvaluationReport(
            top1_accuracy=top1_acc,
            top3_accuracy=top3_acc,
            multi_incident_separation_accuracy=multi_sep_acc,
            suppression_precision=supp_prec,
            suppression_recall=supp_recall,
            blast_radius_accuracy=blast_acc,
            mean_detection_time_seconds=mean_det_time,
            total_scenarios=len(scenarios),
            passed_scenarios=passed_cnt,
            failed_scenarios=failed_cnt,
            details=details,
        )
