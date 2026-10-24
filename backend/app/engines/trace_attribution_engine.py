"""OpenTelemetry Distributed Trace Critical-Path Span Attribution Engine.

Decomposes end-to-end distributed traces into parent-child span execution trees,
computes interval-merged exclusive span execution time (accounting for parallel async fan-out),
and isolates the exact operation/SQL/gRPC span responsible for tail latency.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import logging
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class TraceSpan:
    """Single OpenTelemetry-compatible distributed trace span."""
    span_id: str
    trace_id: str
    service_id: str
    operation_name: str
    start_time_ms: float
    duration_ms: float
    parent_span_id: str | None = None
    status_code: str = "OK"  # "OK", "ERROR", "DEADLINE_EXCEEDED"
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class SpanAttributionNode:
    """Computed exclusive latency attribution for a single span."""
    span_id: str
    parent_span_id: str | None
    service_id: str
    operation_name: str
    inclusive_duration_ms: float
    exclusive_duration_ms: float
    exclusive_share_pct: float
    status_code: str
    on_critical_path: bool
    attributes: dict[str, Any] = field(default_factory=dict)


@dataclass
class TraceCriticalPathReport:
    """Complete critical-path latency attribution report for a distributed trace."""
    trace_id: str
    total_trace_duration_ms: float
    bottleneck_service: str
    bottleneck_span_id: str
    bottleneck_operation: str
    bottleneck_exclusive_ms: float
    bottleneck_contribution_pct: float
    critical_path_services: list[str]
    span_attributions: list[SpanAttributionNode]

    def to_dict(self) -> dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "total_trace_duration_ms": round(self.total_trace_duration_ms, 2),
            "bottleneck_service": self.bottleneck_service,
            "bottleneck_span_id": self.bottleneck_span_id,
            "bottleneck_operation": self.bottleneck_operation,
            "bottleneck_exclusive_ms": round(self.bottleneck_exclusive_ms, 2),
            "bottleneck_contribution_pct": round(self.bottleneck_contribution_pct, 2),
            "critical_path_services": self.critical_path_services,
            "span_attributions": [
                {
                    "span_id": n.span_id,
                    "parent_span_id": n.parent_span_id,
                    "service_id": n.service_id,
                    "operation_name": n.operation_name,
                    "inclusive_duration_ms": round(n.inclusive_duration_ms, 2),
                    "exclusive_duration_ms": round(n.exclusive_duration_ms, 2),
                    "exclusive_share_pct": round(n.exclusive_share_pct, 2),
                    "status_code": n.status_code,
                    "on_critical_path": n.on_critical_path,
                    "attributes": n.attributes,
                }
                for n in self.span_attributions
            ],
        }


class TraceAttributionEngine:
    """Computes interval-aware critical-path latency attribution across OpenTelemetry spans."""

    @staticmethod
    def _merged_children_duration(parent: TraceSpan, children: list[TraceSpan]) -> float:
        """Compute total time spent waiting on child spans, merging overlapping parallel intervals."""
        if not children:
            return 0.0

        p_start = parent.start_time_ms
        p_end = parent.start_time_ms + parent.duration_ms

        intervals: list[tuple[float, float]] = []
        for c in children:
            c_start = max(p_start, c.start_time_ms)
            c_end = min(p_end, c.start_time_ms + c.duration_ms)
            if c_end > c_start:
                intervals.append((c_start, c_end))

        if not intervals:
            return 0.0

        intervals.sort(key=lambda x: x[0])
        merged: list[tuple[float, float]] = [intervals[0]]
        for cur_s, cur_e in intervals[1:]:
            prev_s, prev_e = merged[-1]
            if cur_s <= prev_e:
                merged[-1] = (prev_s, max(prev_e, cur_e))
            else:
                merged.append((cur_s, cur_e))

        return sum(e - s for s, e in merged)

    def analyze_trace(self, spans: list[TraceSpan]) -> TraceCriticalPathReport:
        """Decompose a trace into exclusive span latencies and isolate the bottleneck span."""
        if not spans:
            raise ValueError("Cannot analyze an empty span list.")

        trace_id = spans[0].trace_id
        span_map = {s.span_id: s for s in spans}
        children_map: dict[str, list[TraceSpan]] = {s.span_id: [] for s in spans}

        roots: list[TraceSpan] = []
        for s in spans:
            if s.parent_span_id and s.parent_span_id in children_map:
                children_map[s.parent_span_id].append(s)
            else:
                roots.append(s)

        root_span = max(roots, key=lambda s: s.duration_ms) if roots else max(spans, key=lambda s: s.duration_ms)
        total_duration = max(root_span.duration_ms, 1e-6)

        # Compute exclusive duration for every span
        exclusive_by_id: dict[str, float] = {}
        for s in spans:
            child_wait = self._merged_children_duration(s, children_map.get(s.span_id, []))
            exclusive_by_id[s.span_id] = max(0.0, s.duration_ms - child_wait)

        # Identify the bottleneck span (highest exclusive self-time, weighted slightly by error status)
        def _bottleneck_score(s: TraceSpan) -> float:
            excl = exclusive_by_id[s.span_id]
            err_boost = 1.15 if s.status_code != "OK" else 1.0
            return excl * err_boost

        bottleneck_span = max(spans, key=_bottleneck_score)
        bottleneck_excl = exclusive_by_id[bottleneck_span.span_id]
        bottleneck_pct = min(100.0, (bottleneck_excl / total_duration) * 100.0)
        logger.debug(
            "Analyzed %d spans; bottleneck isolated: %s (%s) with exclusive self-time %.2fms (%.1f%%)",
            len(spans),
            bottleneck_span.service_id,
            bottleneck_span.operation_name,
            bottleneck_excl,
            bottleneck_pct,
        )

        # Reconstruct critical path from root down to bottleneck leaf
        critical_span_ids: set[str] = set()
        curr: TraceSpan | None = bottleneck_span
        path_services_rev: list[str] = []
        while curr is not None:
            critical_span_ids.add(curr.span_id)
            if not path_services_rev or path_services_rev[-1] != curr.service_id:
                path_services_rev.append(curr.service_id)
            curr = span_map.get(curr.parent_span_id) if curr.parent_span_id else None

        critical_path_services = list(reversed(path_services_rev))

        attributions: list[SpanAttributionNode] = []
        for s in sorted(spans, key=lambda x: exclusive_by_id[x.span_id], reverse=True):
            excl = exclusive_by_id[s.span_id]
            share_pct = min(100.0, (excl / total_duration) * 100.0)
            attributions.append(
                SpanAttributionNode(
                    span_id=s.span_id,
                    parent_span_id=s.parent_span_id,
                    service_id=s.service_id,
                    operation_name=s.operation_name,
                    inclusive_duration_ms=s.duration_ms,
                    exclusive_duration_ms=excl,
                    exclusive_share_pct=share_pct,
                    status_code=s.status_code,
                    on_critical_path=(s.span_id in critical_span_ids),
                    attributes=dict(s.attributes),
                )
            )

        return TraceCriticalPathReport(
            trace_id=trace_id,
            total_trace_duration_ms=total_duration,
            bottleneck_service=bottleneck_span.service_id,
            bottleneck_span_id=bottleneck_span.span_id,
            bottleneck_operation=bottleneck_span.operation_name,
            bottleneck_exclusive_ms=bottleneck_excl,
            bottleneck_contribution_pct=bottleneck_pct,
            critical_path_services=critical_path_services,
            span_attributions=attributions,
        )

    def synthesize_cascade_trace(
        self,
        trace_id: str = "trace-otel-9941a",
        root_cause_service: str = "payment-service",
        fault_type: str = "db_pool_exhaustion",
    ) -> list[TraceSpan]:
        """Synthesize a realistic multi-hop OpenTelemetry distributed trace for a cascading incident."""
        op_map = {
            "db_pool_exhaustion": (
                "PostgreSQL SELECT * FROM payment_ledger WHERE tx_id = $1 FOR UPDATE",
                {"db.system": "postgresql", "db.pool.active": 100, "db.pool.max": 100, "db.wait_time_ms": 815.0},
            ),
            "memory_leak": (
                "JVM FullGC Stop-The-World Pause (Tenured Gen 99.4%)",
                {"jvm.gc.collector": "G1OldGeneration", "jvm.heap.used_pct": 99.4},
            ),
            "cpu_spike": (
                "CryptoTLS RSA-4096 Synchronous Signature Verification Loop",
                {"thread.cpu_utilization": 98.7, "worker.queue_depth": 412},
            ),
            "network_latency": (
                "gRPC /stripe.Gateway/AuthorizeCard (TCP Retransmission Backoff)",
                {"rpc.system": "grpc", "net.packet_loss_pct": 18.5},
            ),
        }
        bottleneck_op, bottleneck_attrs = op_map.get(
            fault_type,
            ("DBAcquireConnectionPoolWait", {"fault_type": fault_type}),
        )

        return [
            TraceSpan(
                span_id="span-gw-01",
                parent_span_id=None,
                trace_id=trace_id,
                service_id="api-gateway",
                operation_name="POST /api/v1/checkout",
                start_time_ms=0.0,
                duration_ms=920.0,
                status_code="ERROR",
                attributes={"http.method": "POST", "http.status_code": 504},
            ),
            TraceSpan(
                span_id="span-auth-02",
                parent_span_id="span-gw-01",
                trace_id=trace_id,
                service_id="auth-service",
                operation_name="gRPC /auth.TokenVerifier/VerifyJWT",
                start_time_ms=2.0,
                duration_ms=8.0,
                status_code="OK",
                attributes={"rpc.system": "grpc"},
            ),
            TraceSpan(
                span_id="span-ord-03",
                parent_span_id="span-gw-01",
                trace_id=trace_id,
                service_id="order-service",
                operation_name="gRPC /order.OrderManager/CreateOrder",
                start_time_ms=12.0,
                duration_ms=895.0,
                status_code="ERROR",
                attributes={"rpc.system": "grpc", "retry.attempts": 2},
            ),
            TraceSpan(
                span_id="span-inv-04",
                parent_span_id="span-ord-03",
                trace_id=trace_id,
                service_id="inventory-service",
                operation_name="gRPC /inventory.Stock/ReserveItems",
                start_time_ms=15.0,
                duration_ms=18.0,
                status_code="OK",
                attributes={"rpc.system": "grpc"},
            ),
            TraceSpan(
                span_id="span-root-05",
                parent_span_id="span-ord-03",
                trace_id=trace_id,
                service_id=root_cause_service,
                operation_name=bottleneck_op,
                start_time_ms=35.0,
                duration_ms=865.0,
                status_code="DEADLINE_EXCEEDED",
                attributes=bottleneck_attrs,
            ),
        ]
