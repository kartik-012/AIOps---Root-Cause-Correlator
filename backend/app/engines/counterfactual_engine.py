"""Counterfactual Engine — What-If re-simulation of incident cascades under hypothetical parameter changes.

Re-evaluates whether a cascade would still occur if a given service's metric was capped or mitigated.
"""

from dataclasses import dataclass
from typing import Any

from app.engines.correlation_engine import AnomalyEvent, CorrelationEngine
from app.graph.dependency_graph import DependencyGraph


@dataclass
class CounterfactualSimulationResult:
    """Result of a counterfactual simulation."""
    would_cascade: bool
    original_affected_services: list[str]
    simulated_affected_services: list[str]
    original_root_cause: str | None
    simulated_root_cause: str | None
    mitigated_nodes: list[str]


class CounterfactualEngine:
    """Simulates what-if scenarios by perturbing metric data and observing graph cascade propagation."""

    def __init__(self, dependency_graph: DependencyGraph):
        self.dep_graph = dependency_graph
        self.correlation_engine = CorrelationEngine(dependency_graph)

    def simulate(
        self,
        original_anomalies: list[AnomalyEvent],
        modified_service_id: str,
        modified_metric: str,
        capped_value: float,
        normal_threshold: float = 2.0,
    ) -> CounterfactualSimulationResult:
        """Re-run correlation logic on perturbed anomaly trace.

        If the capped_value reduces the metric below the anomaly threshold,
        the anomaly on (modified_service_id, modified_metric) is removed or downgraded.
        Downstream propagated anomalies that depended on this anomaly are then evaluated.
        """
        original_correlations = self.correlation_engine.correlate(original_anomalies)
        original_affected = set()
        orig_root = None
        if original_correlations:
            orig_root = original_correlations[0].root_cause_service_id
            for inc in original_correlations:
                original_affected.update(inc.affected_service_ids)
                original_affected.add(inc.root_cause_service_id)

        # Filter out anomalies that are mitigated by the parameter cap
        simulated_anomalies: list[AnomalyEvent] = []
        for a in original_anomalies:
            if a.service_id == modified_service_id and a.metric_type == modified_metric:
                # If capped value is nominal (e.g. low latency / low error rate), anomaly is prevented
                if capped_value <= normal_threshold:
                    continue  # Anomaly prevented!
                else:
                    # Downgrade z_score
                    simulated_anomalies.append(
                        AnomalyEvent(
                            service_id=a.service_id,
                            metric_type=a.metric_type,
                            z_score=min(a.z_score, capped_value),
                            severity="medium" if capped_value < 3.0 else a.severity,
                            detected_at=a.detected_at,
                        )
                    )
            else:
                simulated_anomalies.append(a)

        # If the root cause anomaly was eliminated, callers that were only suffering secondary cascade
        # will not trigger anomalies
        if modified_service_id == orig_root and capped_value <= normal_threshold:
            # All downstream cascade from this root is mitigated
            simulated_anomalies = [
                a for a in simulated_anomalies
                if a.service_id not in self.dep_graph.get_all_upstream_callers(modified_service_id)
            ]

        simulated_correlations = self.correlation_engine.correlate(simulated_anomalies)
        simulated_affected = set()
        sim_root = None
        if simulated_correlations:
            sim_root = simulated_correlations[0].root_cause_service_id
            for inc in simulated_correlations:
                simulated_affected.update(inc.affected_service_ids)
                simulated_affected.add(inc.root_cause_service_id)

        mitigated = original_affected - simulated_affected
        would_cascade = len(simulated_affected) > 1

        return CounterfactualSimulationResult(
            would_cascade=would_cascade,
            original_affected_services=sorted(list(original_affected)),
            simulated_affected_services=sorted(list(simulated_affected)),
            original_root_cause=orig_root,
            simulated_root_cause=sim_root,
            mitigated_nodes=sorted(list(mitigated)),
        )
