"""Prediction Engine — Blast radius forward walk with ETA and spread probability.

Forecasts cascade propagation downstream from currently anomalous nodes across the dependency graph.
"""

from dataclasses import dataclass
from typing import Any
import networkx as nx

from app.graph.dependency_graph import DependencyGraph


@dataclass
class BlastRadiusPredictionItem:
    """A predicted downstream service impact."""
    service_id: str
    service_name: str
    distance: int
    eta_seconds: int
    confidence: float


@dataclass
class BlastRadiusResult:
    """Complete prediction engine output for an active incident."""
    incident_id: str
    root_cause_service_id: str
    predictions: list[BlastRadiusPredictionItem]
    contained: bool


class PredictionEngine:
    """Predicts which downstream microservices will be impacted next and when."""

    # Non-critical, asynchronous/leaf services that do not propagate sync cascades
    NON_CASCADING_SERVICES = {"notification"}

    def __init__(self, dependency_graph: DependencyGraph, default_hop_time_seconds: int = 30):
        self.dep_graph = dependency_graph
        self.default_hop_time_seconds = default_hop_time_seconds

    def predict_blast_radius(
        self,
        incident_id: str,
        root_cause_service_id: str,
        already_affected_service_ids: list[str] | set[str] | None = None,
        observed_hop_times: list[float] | None = None,
    ) -> BlastRadiusResult:
        """Walk forward through callers/dependents and compute ETAs and risk."""
        # If the root cause is a non-cascading async leaf (like notification), predict contained failure
        if root_cause_service_id in self.NON_CASCADING_SERVICES:
            return BlastRadiusResult(
                incident_id=incident_id,
                root_cause_service_id=root_cause_service_id,
                predictions=[],
                contained=True,
            )

        affected = set(already_affected_service_ids) if already_affected_service_ids else set()
        affected.add(root_cause_service_id)

        if observed_hop_times and len(observed_hop_times) > 0:
            avg_hop_time = int(sum(observed_hop_times) / len(observed_hop_times))
            avg_hop_time = max(avg_hop_time, 5)
        else:
            avg_hop_time = self.default_hop_time_seconds

        predictions: list[BlastRadiusPredictionItem] = []

        callers = self.dep_graph.get_all_upstream_callers(root_cause_service_id)
        callees = self.dep_graph.get_all_downstream_reach(root_cause_service_id)
        candidates = (callers | callees) - affected

        if not candidates:
            return BlastRadiusResult(
                incident_id=incident_id,
                root_cause_service_id=root_cause_service_id,
                predictions=[],
                contained=True,
            )

        for candidate_id in candidates:
            d1 = self.dep_graph.get_shortest_path_distance(candidate_id, root_cause_service_id)
            d2 = self.dep_graph.get_shortest_path_distance(root_cause_service_id, candidate_id)
            
            distances = [d for d in [d1, d2] if d is not None]
            if distances:
                min_dist = min(distances)
            else:
                continue

            eta = min_dist * avg_hop_time
            confidence = round(1.0 / (1.0 + 0.45 * min_dist), 2)

            node_data = self.dep_graph.get_node_data(candidate_id)
            name = node_data.get("name", candidate_id)

            predictions.append(
                BlastRadiusPredictionItem(
                    service_id=candidate_id,
                    service_name=name,
                    distance=min_dist,
                    eta_seconds=eta,
                    confidence=confidence,
                )
            )

        predictions.sort(key=lambda x: (x.eta_seconds, -x.confidence))

        return BlastRadiusResult(
            incident_id=incident_id,
            root_cause_service_id=root_cause_service_id,
            predictions=predictions,
            contained=len(predictions) == 0,
        )
