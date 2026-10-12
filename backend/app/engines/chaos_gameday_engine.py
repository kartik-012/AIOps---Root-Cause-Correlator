"""Automated Chaos GameDay Scenario Runner (Feature D).

Executes an end-to-end multi-stage production crisis drill across the entire AIOps pipeline:
1. Fault & Canary Change Injection on the microservice mesh.
2. EWMA / Diurnal Anomaly Detection across cascading telemetry streams (measuring MTTD).
3. MicroRCA++ Edge-Weighted Graph Correlation + OpenTelemetry Trace Critical-Path Span Attribution (measuring MTTI).
4. Canary Remediation Safety Circuit-Breaker + Online Thompson Sampling Bandit feedback loop (measuring MTTR).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
import time
from typing import Any

from app.engines.detection_engine import DetectionEngine
from app.engines.correlation_engine import CorrelationEngine, AnomalyEvent, ChangeEvent
from app.engines.trace_attribution_engine import TraceAttributionEngine
from app.engines.remediation_engine import RemediationEngine
from app.graph.dependency_graph import DependencyGraph
from app.grpc_services.service_states import ServiceStateManager


@dataclass
class GameDayReport:
    """Comprehensive execution report from an automated Chaos GameDay drill."""
    gameday_id: str
    scenario_name: str
    injected_root_service: str
    isolated_root_service: str
    root_cause_accurate: bool
    confidence: float
    mttd_ms: float
    mtti_ms: float
    mttr_ms: float
    total_drill_duration_ms: float
    trace_critical_path: dict[str, Any]
    canary_remediation: dict[str, Any]
    bandit_posterior: dict[str, Any]
    timeline_stages: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "gameday_id": self.gameday_id,
            "scenario_name": self.scenario_name,
            "injected_root_service": self.injected_root_service,
            "isolated_root_service": self.isolated_root_service,
            "root_cause_accurate": self.root_cause_accurate,
            "confidence": round(self.confidence, 4),
            "mttd_ms": round(self.mttd_ms, 3),
            "mtti_ms": round(self.mtti_ms, 3),
            "mttr_ms": round(self.mttr_ms, 3),
            "total_drill_duration_ms": round(self.total_drill_duration_ms, 3),
            "trace_critical_path": self.trace_critical_path,
            "canary_remediation": self.canary_remediation,
            "bandit_posterior": self.bandit_posterior,
            "timeline_stages": self.timeline_stages,
        }


class ChaosGameDayEngine:
    """Orchestrates end-to-end automated SRE Chaos GameDay exercises."""

    def __init__(self, state_manager: ServiceStateManager | None = None):
        self.state_manager = state_manager or ServiceStateManager()
        self.trace_engine = TraceAttributionEngine()
        self.remediation_engine = RemediationEngine(state_manager=self.state_manager)

    @staticmethod
    def _build_default_graph() -> DependencyGraph:
        nodes = [
            {"id": "api-gateway", "name": "api-gateway", "revenue_weight": 10.0},
            {"id": "auth-service", "name": "auth-service", "revenue_weight": 7.0},
            {"id": "product-catalog", "name": "product-catalog", "revenue_weight": 6.0},
            {"id": "inventory-service", "name": "inventory-service", "revenue_weight": 8.0},
            {"id": "order-service", "name": "order-service", "revenue_weight": 9.0},
            {"id": "payment-service", "name": "payment-service", "revenue_weight": 10.0},
        ]
        edges = [
            {"from": "api-gateway", "to": "auth-service"},
            {"from": "api-gateway", "to": "product-catalog"},
            {"from": "product-catalog", "to": "inventory-service"},
            {"from": "api-gateway", "to": "order-service"},
            {"from": "order-service", "to": "payment-service"},
            {"from": "order-service", "to": "inventory-service"},
        ]
        graph = DependencyGraph.from_nodes_and_edges(nodes, edges)
        # Apply realistic RPS + empirical covariance edge weights (MicroRCA++)
        graph.set_edge_weight("order-service", "payment-service", rps=480.0, covariance=0.94)
        graph.set_edge_weight("api-gateway", "order-service", rps=520.0, covariance=0.89)
        graph.set_edge_weight("order-service", "inventory-service", rps=140.0, covariance=0.18)
        return graph

    async def run_gameday_drill(
        self,
        scenario_name: str = "db_pool_exhaustion",
        root_service: str = "payment-service",
    ) -> GameDayReport:
        """Execute a full 4-stage Chaos GameDay drill and return measured SRE telemetry."""
        t_drill_start = time.perf_counter()
        t0 = datetime.now(timezone.utc)
        timeline: list[dict[str, Any]] = []

        # Stage 1: Inject fault into ServiceStateManager
        self.state_manager.inject_fault(root_service, scenario_name)
        timeline.append(
            {
                "stage": "1_FAULT_INJECTION",
                "service": root_service,
                "fault_type": scenario_name,
                "status": "INJECTED",
            }
        )

        # Stage 2: Streaming EWMA Detection (measure MTTD)
        t_det_start = time.perf_counter()
        det_engine = DetectionEngine(alpha=0.3, base_threshold=2.5, min_samples=3, redis_client=None)
        cascade_services = [root_service, "order-service", "api-gateway"]
        for svc in cascade_services:
            for i in range(5):
                det_engine.process_metric(
                    svc,
                    "latency_ms",
                    50.0 + (0.8 if i % 2 == 0 else -0.8),
                    t0 - timedelta(seconds=(5 - i) * 10),
                )

        spikes = [
            (root_service, "latency_ms", 890.0, t0),
            ("order-service", "latency_ms", 540.0, t0 + timedelta(seconds=4)),
            ("api-gateway", "latency_ms", 460.0, t0 + timedelta(seconds=8)),
        ]
        detected_anomalies: list[AnomalyEvent] = []
        for svc, metric, val, ts in spikes:
            res = det_engine.process_metric(svc, metric, val, ts)
            if res.is_anomaly:
                detected_anomalies.append(
                    AnomalyEvent(
                        service_id=svc,
                        metric_type=metric,
                        z_score=res.z_score,
                        severity=res.severity,
                        detected_at=ts,
                    )
                )
        mttd_ms = (time.perf_counter() - t_det_start) * 1000.0
        timeline.append(
            {
                "stage": "2_STREAMING_DETECTION",
                "anomalies_flagged": len(detected_anomalies),
                "mttd_ms": round(mttd_ms, 3),
            }
        )

        # Stage 3: MicroRCA++ Graph Correlation + OpenTelemetry Trace Critical-Path Attribution (measure MTTI)
        t_iso_start = time.perf_counter()
        graph = self._build_default_graph()
        corr_engine = CorrelationEngine(graph)
        change_events = [
            ChangeEvent(
                service_id=root_service,
                git_sha="a8f31c9-canary",
                deployed_at=t0 - timedelta(minutes=6),
                config_version="v2.4.0-canary",
            )
        ]
        corr_results = corr_engine.correlate(detected_anomalies, change_events=change_events)
        top_corr = corr_results[0]
        isolated_root = top_corr.root_cause_service_id
        confidence = top_corr.confidence

        spans = self.trace_engine.synthesize_cascade_trace(
            trace_id="trace-gameday-01",
            root_cause_service=root_service,
            fault_type=scenario_name,
        )
        trace_report = self.trace_engine.analyze_trace(spans)
        mtti_ms = (time.perf_counter() - t_iso_start) * 1000.0
        timeline.append(
            {
                "stage": "3_CAUSAL_ISOLATION_AND_TRACE_ATTRIBUTION",
                "isolated_root_service": isolated_root,
                "bottleneck_span_operation": trace_report.bottleneck_operation,
                "mtti_ms": round(mtti_ms, 3),
            }
        )

        # Stage 4: Canary Remediation Safety Circuit-Breaker + Thompson Sampling Bandit Update (measure MTTR)
        t_rem_start = time.perf_counter()
        plan = self.remediation_engine.generate_plan(
            incident_id="inc-gameday-01",
            root_cause_type=scenario_name,
            target_service=isolated_root,
        )
        executed_plan = await self.remediation_engine.execute_canary_with_safety_circuit_breaker(
            plan_id=plan.plan_id,
            approver="ChaosGameDayAutoCommander",
            canary_percent=5,
            verify_health=True,
        )
        mttr_ms = (time.perf_counter() - t_rem_start) * 1000.0
        bandit_post = self.remediation_engine.bandit.record_outcome(
            root_cause_type=scenario_name,
            action_id=executed_plan.action_title,
            resolved=(executed_plan.canary_status == "CANARY_SUCCESS"),
            mttr_seconds=max(mttr_ms / 1000.0, 0.001),
        )
        timeline.append(
            {
                "stage": "4_CANARY_REMEDIATION_AND_BANDIT_LEARNING",
                "canary_status": executed_plan.canary_status,
                "closed_loop_verified": executed_plan.closed_loop_verified,
                "mttr_ms": round(mttr_ms, 3),
            }
        )

        total_ms = (time.perf_counter() - t_drill_start) * 1000.0
        return GameDayReport(
            gameday_id=f"gameday-{int(t0.timestamp())}",
            scenario_name=scenario_name,
            injected_root_service=root_service,
            isolated_root_service=isolated_root,
            root_cause_accurate=(isolated_root == root_service),
            confidence=confidence,
            mttd_ms=mttd_ms,
            mtti_ms=mtti_ms,
            mttr_ms=mttr_ms,
            total_drill_duration_ms=total_ms,
            trace_critical_path=trace_report.to_dict(),
            canary_remediation=executed_plan.to_dict(),
            bandit_posterior=bandit_post,
            timeline_stages=timeline,
        )
