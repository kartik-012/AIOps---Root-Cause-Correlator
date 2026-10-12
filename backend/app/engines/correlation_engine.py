"""Correlation Engine — Graph-based root cause identification with multi-incident separation.

Uses NetworkX dependency topology to isolate independent incident components
and locate the causal root for each component via graph topology and temporal precedence.
Handles adversarial cases where independent root causes converge on a shared caller.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone
import math
import uuid
from typing import Any
import networkx as nx
import numpy as np

from app.graph.dependency_graph import DependencyGraph
from app.engines.suppression_engine import build_signature


@dataclass
class LaggedCorrelationResult:
    """Result of tau-shifted Pearson & Spearman cross-correlation between two metric streams."""
    cause_service_id: str
    effect_service_id: str
    optimal_lag_steps: int
    max_pearson_r: float
    max_spearman_rho: float
    combined_score: float
    is_causally_aligned: bool
    lag_profile: dict[int, float] = field(default_factory=dict)


def _rank_array(arr: np.ndarray) -> np.ndarray:
    """Compute average ranks (1-based) for Spearman rank correlation."""
    n = len(arr)
    if n == 0:
        return arr
    order = np.argsort(arr, kind="mergesort")
    ranks = np.empty(n, dtype=float)
    i = 0
    while i < n:
        j = i
        while j + 1 < n and arr[order[j + 1]] == arr[order[i]]:
            j += 1
        avg_rank = 0.5 * (i + j) + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg_rank
        i = j + 1
    return ranks


def _pearson_corr(x: np.ndarray, y: np.ndarray) -> float:
    """Compute Pearson correlation coefficient r in [-1.0, 1.0] with zero-variance protection."""
    if len(x) < 3 or len(x) != len(y):
        return 0.0
    xm = x - np.mean(x)
    ym = y - np.mean(y)
    denom = float(np.linalg.norm(xm) * np.linalg.norm(ym))
    if denom <= 1e-12:
        return 0.0
    r = float(np.dot(xm, ym) / denom)
    return float(max(-1.0, min(1.0, r)))


def _spearman_corr(x: np.ndarray, y: np.ndarray) -> float:
    """Compute Spearman rank correlation rho in [-1.0, 1.0] for monotonic non-linear cascades."""
    if len(x) < 3 or len(x) != len(y):
        return 0.0
    return _pearson_corr(_rank_array(x), _rank_array(y))


def compute_lagged_cross_correlation(
    series_cause: list[float],
    series_effect: list[float],
    max_lag: int = 5,
    cause_service_id: str = "callee",
    effect_service_id: str = "caller",
    alignment_threshold: float = 0.65,
) -> LaggedCorrelationResult:
    """Compute time-lagged cross-correlation r(tau) and rho(tau) across lags [-max_lag, +max_lag].

    Positive lag tau >= 0 tests whether `series_cause[t]` leads `series_effect[t + tau]`.
    Negative lag tau < 0 tests the reverse direction (`series_effect` leading `series_cause`).
    """
    n = min(len(series_cause), len(series_effect))
    if n < 4:
        return LaggedCorrelationResult(
            cause_service_id=cause_service_id,
            effect_service_id=effect_service_id,
            optimal_lag_steps=0,
            max_pearson_r=0.0,
            max_spearman_rho=0.0,
            combined_score=0.0,
            is_causally_aligned=False,
            lag_profile={},
        )

    x_full = np.asarray(series_cause[:n], dtype=float)
    y_full = np.asarray(series_effect[:n], dtype=float)
    eff_max_lag = min(max(0, int(max_lag)), n - 3)

    lag_profile: dict[int, float] = {}
    best_forward_lag = 0
    best_forward_pearson = -1.0
    best_forward_spearman = -1.0
    best_forward_combined = -1.0
    best_reverse_combined = -1.0

    for tau in range(-eff_max_lag, eff_max_lag + 1):
        if tau > 0:
            x_slice = x_full[: n - tau]
            y_slice = y_full[tau:n]
        elif tau < 0:
            abs_tau = abs(tau)
            x_slice = x_full[abs_tau:n]
            y_slice = y_full[: n - abs_tau]
        else:
            x_slice = x_full
            y_slice = y_full

        p_r = _pearson_corr(x_slice, y_slice)
        s_rho = _spearman_corr(x_slice, y_slice)
        comb = round(max(p_r, s_rho), 4)
        lag_profile[tau] = comb

        if tau >= 0:
            if comb > best_forward_combined:
                best_forward_combined = comb
                best_forward_lag = tau
                best_forward_pearson = round(p_r, 4)
                best_forward_spearman = round(s_rho, 4)
        else:
            if comb > best_reverse_combined:
                best_reverse_combined = comb

    # Causal alignment holds when forward lag correlation is strong (>= threshold)
    # and is not strictly dominated by a reverse-direction lag
    is_aligned = (
        best_forward_combined >= alignment_threshold
        and best_forward_combined >= (best_reverse_combined - 0.05)
    )

    return LaggedCorrelationResult(
        cause_service_id=cause_service_id,
        effect_service_id=effect_service_id,
        optimal_lag_steps=best_forward_lag,
        max_pearson_r=max(0.0, best_forward_pearson),
        max_spearman_rho=max(0.0, best_forward_spearman),
        combined_score=max(0.0, best_forward_combined),
        is_causally_aligned=is_aligned,
        lag_profile=lag_profile,
    )


@dataclass
class ChangeEvent:
    """Input deployment or configuration change event (Git SHA / Config Rollout)."""
    service_id: str
    git_sha: str
    deployed_at: datetime
    config_version: str | None = None
    deployed_by: str | None = None
    environment: str = "production"
    id: str = field(default_factory=lambda: str(uuid.uuid4()))


@dataclass
class CorrelatedChangeEvent:
    """Matched deployment event occurring within the pre-anomaly window (default <= 15 min)."""
    service_id: str
    git_sha: str
    config_version: str | None
    deployed_by: str | None
    deployed_at: datetime
    minutes_before_onset: float
    proximity_boost: float


def find_correlating_deployment(
    service_id: str,
    anomaly_onset: datetime,
    change_events: list[ChangeEvent] | None,
    window_minutes: float = 15.0,
) -> CorrelatedChangeEvent | None:
    """Find the most recent ChangeEvent on `service_id` within [0, window_minutes] before `anomaly_onset`.

    Applies an exponential temporal proximity boost:
        boost = 0.15 * exp(-minutes_before_onset / 10.0)
    """
    if not change_events:
        return None

    best_match: CorrelatedChangeEvent | None = None
    min_delta_sec: float | None = None
    max_window_sec = max(0.0, float(window_minutes) * 60.0)

    for ev in change_events:
        if ev.service_id != service_id:
            continue
        delta_sec = (anomaly_onset - ev.deployed_at).total_seconds()
        # Must occur prior to or at anomaly onset (delta_sec >= 0) and within window
        if 0.0 <= delta_sec <= max_window_sec:
            if min_delta_sec is None or delta_sec < min_delta_sec:
                min_delta_sec = delta_sec
                mins_before = round(delta_sec / 60.0, 2)
                boost = round(0.15 * math.exp(-mins_before / 10.0), 4)
                best_match = CorrelatedChangeEvent(
                    service_id=ev.service_id,
                    git_sha=ev.git_sha,
                    config_version=ev.config_version,
                    deployed_by=ev.deployed_by,
                    deployed_at=ev.deployed_at,
                    minutes_before_onset=mins_before,
                    proximity_boost=boost,
                )

    return best_match


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
    lagged_correlations: list[LaggedCorrelationResult] = field(default_factory=list)
    suspect_deployment: CorrelatedChangeEvent | None = None
    pagerank_scores: dict[str, float] = field(default_factory=dict)
    cycle_detected: bool = False


def compute_personalized_pagerank_scores(
    subgraph: nx.DiGraph,
    service_earliest: dict[str, AnomalyEvent],
    alpha: float = 0.55,
    tau_seconds: float = 15.0,
    max_iter: int = 100,
    tol: float = 1e-6,
) -> dict[str, float]:
    """Compute cycle-safe Personalized PageRank causal scores on the anomalous subgraph.

    Personalization vector p(u) combines anomaly severity |Z_u| and exponential temporal
    precedence exp(-delta_t_u / tau_seconds). Sink nodes receive a self-loop so downstream
    fault sinks retain incoming causal walk mass while cyclic SCCs rank by topological flow + p(u).
    """
    nodes = sorted(subgraph.nodes())
    n = len(nodes)
    if n == 0:
        return {}
    if n == 1:
        return {nodes[0]: 1.0}

    min_ts = min(
        (service_earliest[u].detected_at for u in nodes if u in service_earliest),
        default=datetime.now(timezone.utc),
    )

    raw_weights: dict[str, float] = {}
    for u in nodes:
        ev = service_earliest.get(u)
        if ev is not None:
            delta_sec = max(0.0, (ev.detected_at - min_ts).total_seconds())
            sev = max(abs(float(ev.z_score)), 0.1)
            raw_weights[u] = sev * math.exp(-delta_sec / max(tau_seconds, 1.0))
        else:
            raw_weights[u] = 0.1

    total_w = sum(raw_weights.values()) or 1.0
    personalization = {u: raw_weights[u] / total_w for u in nodes}

    # Build transition graph where sink nodes have self-loops to accumulate downstream flow
    work_g = subgraph.copy()
    for u in nodes:
        if work_g.out_degree(u) == 0:
            work_g.add_edge(u, u)

    # Power-iteration Personalized PageRank (zero external SciPy requirement)
    scores = dict(personalization)
    for _ in range(max_iter):
        prev = scores.copy()
        next_scores = {u: (1.0 - alpha) * personalization[u] for u in nodes}
        for u in nodes:
            out_neighbors = list(work_g.successors(u))
            deg = len(out_neighbors)
            if deg > 0:
                share = alpha * (prev[u] / deg)
                for v in out_neighbors:
                    next_scores[v] += share
            else:
                for v in nodes:
                    next_scores[v] += alpha * prev[u] * personalization[v]

        diff = sum(abs(next_scores[u] - prev[u]) for u in nodes)
        scores = next_scores
        if diff < tol:
            break

    total_s = sum(scores.values()) or 1.0
    return {u: round(scores[u] / total_s, 4) for u in nodes}


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
        """Compute root cause confidence from severity, temporal priority, and topology."""
        abs_z = abs(earliest_anomaly.z_score)
        severity_score = min(abs_z / 6.0, 1.0)

        # Compute real temporal precedence score in [0.0, 1.0] across the component's anomalies
        if all_component_anomalies:
            min_ts = min(a.detected_at for a in all_component_anomalies)
            max_ts = max(a.detected_at for a in all_component_anomalies)
            span_sec = (max_ts - min_ts).total_seconds()
            if span_sec > 0.0:
                lag_sec = max(0.0, (earliest_anomaly.detected_at - min_ts).total_seconds())
                precedence_score = max(0.0, 1.0 - (lag_sec / span_sec))
            else:
                precedence_score = 1.0
        else:
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
        metric_streams: dict[str, list[float]] | None = None,
        change_events: list[ChangeEvent] | None = None,
        deploy_window_minutes: float = 15.0,
    ) -> list[CorrelatedIncident]:
        """Correlate active anomalies into one or more incidents, verifying lagged cross-correlation and change-event overlays."""
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

            # Differentiator #6: Cycle-Safe Causal Ranking via Personalized PageRank & Terminal SCCs
            comp_subgraph = subgraph.subgraph(comp_services).copy()
            cycle_detected = self.dep_graph.has_cycles(comp_subgraph)
            ppr_scores = compute_personalized_pagerank_scores(
                subgraph=comp_subgraph,
                service_earliest=service_earliest,
            )

            # Decompose component into Strongly Connected Components (SCCs)
            # A terminal SCC has no outgoing dependency edges to any node outside that SCC.
            sccs = self.dep_graph.get_strongly_connected_components(comp_subgraph)
            candidates: list[str] = []
            for scc in sccs:
                external_downstream: set[str] = set()
                for sid in scc:
                    downstream = self.dep_graph.get_downstream_services(sid).intersection(comp_services)
                    external_downstream.update(downstream - scc)
                if not external_downstream:
                    # Terminal SCC: if single node, add directly; if cycle (|scc| > 1), pick highest PPR node
                    best_in_scc = max(
                        scc,
                        key=lambda s: (
                            ppr_scores.get(s, 0.0),
                            -(service_earliest[s].detected_at.timestamp() if s in service_earliest else float("inf")),
                            abs(service_earliest[s].z_score) if s in service_earliest else 0.0,
                        ),
                    )
                    candidates.append(best_in_scc)

            if not candidates:
                candidates = list(comp_services)

            # Sort candidates deterministically by Personalized PageRank score descending, then earliest onset
            candidates.sort(
                key=lambda s: (
                    -ppr_scores.get(s, 0.0),
                    service_earliest[s].detected_at if s in service_earliest else datetime.max.replace(tzinfo=timezone.utc),
                    s,
                )
            )

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
                independent_roots = [candidates[0]]


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

                # Evaluate tau-shifted Pearson/Spearman cross-correlation when metric streams exist
                lagged_results: list[LaggedCorrelationResult] = []
                if metric_streams and root_cause_sid in metric_streams:
                    cause_series = metric_streams[root_cause_sid]
                    for aff_sid in affected_ids:
                        if aff_sid in metric_streams:
                            res = compute_lagged_cross_correlation(
                                series_cause=cause_series,
                                series_effect=metric_streams[aff_sid],
                                max_lag=5,
                                cause_service_id=root_cause_sid,
                                effect_service_id=aff_sid,
                            )
                            lagged_results.append(res)

                    if lagged_results:
                        aligned_count = sum(1 for r in lagged_results if r.is_causally_aligned)
                        if aligned_count > 0:
                            avg_corr = sum(r.combined_score for r in lagged_results if r.is_causally_aligned) / aligned_count
                            confidence = round(min(0.99, confidence + 0.08 * avg_corr), 2)
                        else:
                            # Coincidental uncorrelated spikes receive confidence penalty
                            confidence = round(max(0.10, confidence - 0.12), 2)

                # Differentiator #5: Change-Event Correlation (Git SHA / Config Deploy Overlay)
                suspect_deploy = find_correlating_deployment(
                    service_id=root_cause_sid,
                    anomaly_onset=root_earliest_anomaly.detected_at,
                    change_events=change_events,
                    window_minutes=deploy_window_minutes,
                )
                if suspect_deploy is not None:
                    confidence = round(min(0.99, confidence + suspect_deploy.proximity_boost), 2)

                hour_bucket = float(root_earliest_anomaly.detected_at.hour // 6)
                day_of_week = float(root_earliest_anomaly.detected_at.weekday())
                sev_z = float(abs(root_earliest_anomaly.z_score))
                depth = float(len(propagation_list))
                speed = 10.0
                if len(sorted_by_time) > 1:
                    t_first = service_earliest[sorted_by_time[0]].detected_at
                    t_last = service_earliest[sorted_by_time[-1]].detected_at
                    diff_sec = max((t_last - t_first).total_seconds(), 1.0)
                    speed = round(diff_sec / len(sorted_by_time), 2)

                sig = build_signature(
                    hour_bucket=hour_bucket,
                    day_of_week=day_of_week,
                    service_id=root_cause_sid,
                    metric_type=root_earliest_anomaly.metric_type,
                    severity_z=sev_z,
                    depth=depth,
                    speed=speed,
                )

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
                    "lagged_correlations": lagged_results,
                    "suspect_deployment": suspect_deploy,
                    "pagerank_scores": ppr_scores,
                    "cycle_detected": cycle_detected,
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
                lagged_correlations=r["lagged_correlations"],
                suspect_deployment=r["suspect_deployment"],
                pagerank_scores=r["pagerank_scores"],
                cycle_detected=r["cycle_detected"],
            )
            for r in raw_incidents
        ]

        return correlated_incidents


