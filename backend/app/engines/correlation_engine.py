"""Correlation Engine — Graph-based root cause identification with multi-incident separation.

Uses NetworkX dependency topology to isolate independent incident components
and locate the causal root for each component via graph topology and temporal precedence.
Handles adversarial cases where independent root causes converge on a shared caller.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import uuid
from typing import Any
import networkx as nx

from app.graph.dependency_graph import DependencyGraph


@dataclass
class AnomalyEvent:
    """Input anomaly event to be correlated."""
    service_id: str
    metric_type: str
    z_score: float
    severity: str
    detected_at: datetime
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class AffectedServiceSummary:
    """A service affected in the incident cascade with its propagation order."""
    service_id: str
    service_name: str | None
    propagation_order: int
    affected_at: datetime


@dataclass
class CorrelatedIncident:
    """An identified incident with isolated root cause and propagation chain."""
    incident_id: str
    root_cause_service_id: str
    root_cause_service_name: str
    root_cause_type: str
    confidence: float
    affected_service_ids: list[str]
    affected_services: list[AffectedServiceSummary]
    is_multi_root_cause: bool
    timestamp_start: datetime
    anomalies: list[AnomalyEvent]
    signature: list[float] = field(default_factory=list)


class CorrelationEngine:
    """Correlates anomalies using dependency topology and temporal causality."""

    def __init__(self, dependency_graph: DependencyGraph):
        self.dep_graph = dependency_graph

    def _infer_root_cause_type(self, anomalies_on_node: list[AnomalyEvent]) -> str:
        """Heuristically map anomalous metric types to root cause tags."""
        metric_types = [a.metric_type for a in anomalies_on_node]
        if "connection_pool" in metric_types or "db_connections" in metric_types:
            return "db_connection_exhaustion"
        elif "memory_usage" in metric_types or "heap_used" in metric_types:
            return "memory_leak"
        elif "cpu_usage" in metric_types or "cpu_percent" in metric_types:
            return "cpu_spike"
        elif "latency_ms" in metric_types or "request_latency" in metric_types:
            return "network_latency_injection"
        elif "restart_count" in metric_types or "pod_status" in metric_types:
            return "pod_crash_loop"
        elif "disk_io" in metric_types or "io_wait" in metric_types:
            return "disk_io_saturation"
        elif "error_rate" in metric_types:
            return "config_error"
        return anomalies_on_node[0].metric_type if anomalies_on_node else "unknown_anomaly"

    def _calculate_confidence(
        self,
        candidate_id: str,
        earliest_anomaly: AnomalyEvent,
        all_component_anomalies: list[AnomalyEvent],
        subgraph: nx.DiGraph,
    ) -> float:
        """Compute root cause confidence from severity, time priority, and topology."""
        abs_z = abs(earliest_anomaly.z_score)
        severity_score = min(abs_z / 6.0, 1.0)
        precedence_score = 1.0

        if len(subgraph) > 0:
            centrality = nx.degree_centrality(subgraph).get(candidate_id, 0.5)
        else:
            centrality = 0.5

        confidence = 0.5 * severity_score + 0.3 * precedence_score + 0.2 * centrality
        return round(min(max(confidence, 0.1), 0.99), 2)

    def correlate(
        self,
        anomalies: list[AnomalyEvent],
        is_multi_context: bool = False,
    ) -> list[CorrelatedIncident]:
        """Correlate active anomalies into one or more incidents."""
        if not anomalies:
            return []

        # Group anomalies by service
        service_anomalies: dict[str, list[AnomalyEvent]] = {}
        for a in anomalies:
            service_anomalies.setdefault(a.service_id, []).append(a)

        anomalous_service_ids = set(service_anomalies.keys())

        # Build induced subgraph on anomalous services
        subgraph = self.dep_graph.get_subgraph(anomalous_service_ids)

        # Decompose into weakly connected components
        components = self.dep_graph.get_weakly_connected_components(subgraph)

        raw_incidents: list[dict[str, Any]] = []

        for comp_services in components:
            comp_anomalies = [
                a for a in anomalies if a.service_id in comp_services
            ]
            if not comp_anomalies:
                continue

            # Earliest anomaly per service in this component
            service_earliest: dict[str, AnomalyEvent] = {}
            for sid in comp_services:
                s_anoms = service_anomalies.get(sid, [])
                if s_anoms:
                    earliest_s = min(s_anoms, key=lambda x: x.detected_at)
                    service_earliest[sid] = earliest_s

            # Find all root cause candidates: services with no anomalous downstream dependencies
            candidates: list[str] = []
            for sid in comp_services:
                downstream = self.dep_graph.get_downstream_services(sid)
                anomalous_downstream = downstream.intersection(comp_services)
                if not anomalous_downstream:
                    candidates.append(sid)

            if not candidates:
                candidates = list(comp_services)

            # Check if there are multiple independent root causes in this component
            # (i.e. candidates that have no directed dependency path between each other)
            independent_roots: list[str] = []
            for c in candidates:
                # Check if c is reachable from or reaches any already selected independent root
                has_path = False
                for r in independent_roots:
                    p1 = self.dep_graph.get_shortest_path_distance(c, r)
                    p2 = self.dep_graph.get_shortest_path_distance(r, c)
                    if p1 is not None or p2 is not None:
                        has_path = True
                        break
                if not has_path:
                    independent_roots.append(c)

            if not independent_roots:
                independent_roots = [min(
                    candidates,
                    key=lambda s: service_earliest[s].detected_at if s in service_earliest else datetime.max.replace(tzinfo=timezone.utc),
                )]

            # For each independent root cause, partition the affected services
            for root_cause_sid in independent_roots:
                root_earliest_anomaly = service_earliest[root_cause_sid]
                root_cause_type = self._infer_root_cause_type(service_anomalies.get(root_cause_sid, []))

                # Affected services for this root are its callers/ancestors within the component
                ancestors = self.dep_graph.get_all_upstream_callers(root_cause_sid).intersection(comp_services)
                incident_service_set = {root_cause_sid} | ancestors

                sorted_by_time = sorted(
                    incident_service_set,
                    key=lambda s: service_earliest[s].detected_at if s in service_earliest else datetime.max.replace(tzinfo=timezone.utc),
                )

                propagation_list: list[AffectedServiceSummary] = []
                for order_idx, sid in enumerate(sorted_by_time):
                    node_data = self.dep_graph.get_node_data(sid)
                    sname = node_data.get("name", sid)
                    dt = service_earliest[sid].detected_at if sid in service_earliest else root_earliest_anomaly.detected_at
                    propagation_list.append(
                        AffectedServiceSummary(
                            service_id=sid,
                            service_name=sname,
                            propagation_order=order_idx,
                            affected_at=dt,
                        )
                    )

                confidence = self._calculate_confidence(
                    candidate_id=root_cause_sid,
                    earliest_anomaly=root_earliest_anomaly,
                    all_component_anomalies=comp_anomalies,
                    subgraph=subgraph,
                )

                node_data = self.dep_graph.get_node_data(root_cause_sid)
                root_name = node_data.get("name", root_cause_sid)
                affected_ids = [s for s in sorted_by_time if s != root_cause_sid]

                hour_bucket = float(root_earliest_anomaly.detected_at.hour // 6)
                day_of_week = float(root_earliest_anomaly.detected_at.weekday())
                srv_hash = float((abs(hash(root_cause_sid)) % 100) / 10.0)
                metric_hash = float((abs(hash(root_cause_type)) % 10) / 1.0)
                sev_z = float(abs(root_earliest_anomaly.z_score))
                depth = float(len(propagation_list))
                speed = 10.0
                if len(sorted_by_time) > 1:
                    t_first = service_earliest[sorted_by_time[0]].detected_at
                    t_last = service_earliest[sorted_by_time[-1]].detected_at
                    diff_sec = max((t_last - t_first).total_seconds(), 1.0)
                    speed = round(diff_sec / len(sorted_by_time), 2)

                sig = [hour_bucket, day_of_week, srv_hash, metric_hash, sev_z, depth, speed]

                raw_incidents.append({
                    "incident_id": str(uuid.uuid4()),
                    "root_cause_service_id": root_cause_sid,
                    "root_cause_service_name": root_name,
                    "root_cause_type": root_cause_type,
                    "confidence": confidence,
                    "affected_service_ids": affected_ids,
                    "affected_services": propagation_list,
                    "timestamp_start": root_earliest_anomaly.detected_at,
                    "anomalies": [a for a in comp_anomalies if a.service_id in incident_service_set],
                    "signature": sig,
                })

        is_multi = len(raw_incidents) > 1 or is_multi_context
        correlated_incidents = [
            CorrelatedIncident(
                incident_id=r["incident_id"],
                root_cause_service_id=r["root_cause_service_id"],
                root_cause_service_name=r["root_cause_service_name"],
                root_cause_type=r["root_cause_type"],
                confidence=r["confidence"],
                affected_service_ids=r["affected_service_ids"],
                affected_services=r["affected_services"],
                is_multi_root_cause=is_multi,
                timestamp_start=r["timestamp_start"],
                anomalies=r["anomalies"],
                signature=r["signature"],
            )
            for r in raw_incidents
        ]

        return correlated_incidents
