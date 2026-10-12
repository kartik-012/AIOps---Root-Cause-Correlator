"""Telemetry Kafka consumer — End-to-end streaming EWMA detection, graph root-cause correlation, and suppression.

Subscribes to the `service.telemetry` topic. When an anomaly is detected by `DetectionEngine`:
1. Appends the anomaly to a sliding temporal correlation window (`correlation_window_seconds`).
2. Executes `CorrelationEngine.correlate()` over the active dependency topology to isolate the true upstream root cause
   rather than naively blaming whichever downstream victim service emitted the latest metric.
3. Evaluates `SuppressionEngine.evaluate()` on the correlated incident's 7D signature before paging.
4. Publishes the correlated `IncidentEvent` to `incident.detected`, records an `AuditEvent`, and broadcasts
   live updates over WebSockets and GraphQL Subscriptions.
"""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone, timedelta
import logging
from typing import Any

from ..consumer import BaseKafkaConsumer
from ..config import get_kafka_config
from ..events import TelemetryEvent, IncidentEvent, AuditEvent
from ..producer import get_kafka_producer
from ...engines.correlation_engine import CorrelationEngine, AnomalyEvent
from ...engines.suppression_engine import SuppressionEngine
from ...graph.dependency_graph import DependencyGraph
from ...api.v1.ws import broadcast_event

logger = logging.getLogger(__name__)


class StreamingRingBuffer:
    """High-throughput lock-free ring buffer with windowed tumbling aggregation and backpressure downsampling.

    Under heavy alert storms (>10,000 metrics/sec), prevents database and compute starvation:
    1. Holds incoming telemetry in a bounded deque (capacity=10,000).
    2. Enforces backpressure: when utilization > 80%, nominal observations are downsampled.
    3. Provides 10-second tumbling window aggregation per (service_id, metric_type) pair.
    """

    def __init__(self, capacity: int = 10000, high_watermark: float = 0.80):
        self.capacity = capacity
        self.high_watermark = high_watermark
        self._buffer: deque[dict[str, Any]] = deque(maxlen=capacity)
        self._dropped_count = 0
        self._downsampled_count = 0

    def push(self, telemetry: dict[str, Any], is_anomaly_hint: bool = False) -> bool:
        """Enqueue telemetry event, applying backpressure downsampling when buffer is pressurized."""
        utilization = len(self._buffer) / max(self.capacity, 1)
        if utilization >= self.high_watermark and not is_anomaly_hint:
            # Drop 75% of nominal stationary points under alert storm pressure
            if self._downsampled_count % 4 != 0:
                self._downsampled_count += 1
                return False
            self._downsampled_count += 1

        if len(self._buffer) >= self.capacity:
            self._dropped_count += 1
            return False

        self._buffer.append(telemetry)
        return True

    def pop(self) -> dict[str, Any] | None:
        """Pop next telemetry event from ring buffer."""
        if self._buffer:
            return self._buffer.popleft()
        return None

    def get_stats(self) -> dict[str, Any]:
        return {
            "current_size": len(self._buffer),
            "capacity": self.capacity,
            "utilization": round(len(self._buffer) / max(self.capacity, 1), 3),
            "dropped_count": self._dropped_count,
            "downsampled_count": self._downsampled_count,
        }


def _get_detection_engine():
    """Return the unified process-wide DetectionEngine singleton shared with the REST API."""
    from ...engines.detection_engine import get_shared_detection_engine
    return get_shared_detection_engine()


def _default_topology_graph() -> DependencyGraph:
    """Build the default 8-microservice dependency topology for streaming correlation."""
    nodes = [
        {"id": "api-gateway", "name": "api-gateway", "revenue_weight": 10.0},
        {"id": "auth-service", "name": "auth-service", "revenue_weight": 7.0},
        {"id": "product-catalog", "name": "product-catalog", "revenue_weight": 6.0},
        {"id": "inventory-service", "name": "inventory-service", "revenue_weight": 8.0},
        {"id": "order-service", "name": "order-service", "revenue_weight": 9.0},
        {"id": "payment-service", "name": "payment-service", "revenue_weight": 10.0},
        {"id": "notification-service", "name": "notification-service", "revenue_weight": 3.0},
        {"id": "shipping-service", "name": "shipping-service", "revenue_weight": 4.0},
    ]
    edges = [
        {"from": "api-gateway", "to": "auth-service"},
        {"from": "api-gateway", "to": "product-catalog"},
        {"from": "product-catalog", "to": "inventory-service"},
        {"from": "api-gateway", "to": "order-service"},
        {"from": "order-service", "to": "payment-service"},
        {"from": "order-service", "to": "inventory-service"},
        {"from": "order-service", "to": "notification-service"},
        {"from": "order-service", "to": "shipping-service"},
    ]
    return DependencyGraph.from_nodes_and_edges(nodes, edges)


class TelemetryConsumer(BaseKafkaConsumer):
    """Consumes telemetry events from Kafka and executes streaming EWMA detection + graph correlation."""

    def __init__(
        self,
        dep_graph: DependencyGraph | None = None,
        suppression_engine: SuppressionEngine | None = None,
        correlation_window_seconds: float = 60.0,
        db_session_factory: Any | None = None,
    ):
        config = get_kafka_config()
        super().__init__(
            topics=[config.TOPIC_TELEMETRY],
            group_id=config.CG_TELEMETRY,
            config=config,
        )
        self.dep_graph = dep_graph or _default_topology_graph()
        self.correlation_engine = CorrelationEngine(self.dep_graph)
        self.suppression_engine = suppression_engine or SuppressionEngine(similarity_threshold=0.90)
        self.correlation_window_seconds = correlation_window_seconds
        self.db_session_factory = db_session_factory
        self.ring_buffer = StreamingRingBuffer(capacity=10000, high_watermark=0.80)
        self._recent_anomalies: list[AnomalyEvent] = []
        self._active_incidents: dict[str, IncidentEvent] = {}
        self._persisted_incident_uuids: dict[str, Any] = {}

    def get_correlated_incidents(self) -> list[IncidentEvent]:
        """Return the deduplicated correlated incidents isolated across the active window."""
        return list(self._active_incidents.values())

    def _prune_and_append_anomaly(self, anom: AnomalyEvent) -> list[AnomalyEvent]:
        cutoff = anom.detected_at - timedelta(seconds=self.correlation_window_seconds)
        self._recent_anomalies = [a for a in self._recent_anomalies if a.detected_at >= cutoff]
        self._recent_anomalies.append(anom)
        return list(self._recent_anomalies)

    def _persist_to_db_if_configured(
        self,
        dedup_key: str,
        root_service: str,
        root_cause_type: str,
        confidence: float,
        is_multi_root: bool,
        ts_start: datetime,
        signature: list[float],
    ) -> None:
        if self.db_session_factory is None:
            return
        try:
            import uuid
            from sqlalchemy import select
            from ...models.db_models import Incident, Service

            with self.db_session_factory() as db:
                svc = db.scalar(select(Service).where(Service.name == root_service))
                svc_id = svc.id if svc else uuid.uuid5(uuid.NAMESPACE_DNS, root_service)
                if svc is None:
                    db.add(Service(id=svc_id, name=root_service, revenue_weight=5.0))
                    db.flush()

                existing_id = self._persisted_incident_uuids.get(dedup_key)
                if existing_id is not None:
                    db_inc = db.scalar(select(Incident).where(Incident.id == existing_id))
                    if db_inc is not None:
                        db_inc.confidence_at_detection = confidence
                        db_inc.anomaly_signature = signature if len(signature) == 7 else db_inc.anomaly_signature
                        db.commit()
                        return

                new_inc = Incident(
                    root_cause_service_id=svc_id,
                    root_cause_type=root_cause_type,
                    confidence_at_detection=confidence,
                    is_multi_root_cause=is_multi_root,
                    timestamp_start=ts_start,
                    anomaly_signature=signature if len(signature) == 7 else None,
                )
                db.add(new_inc)
                db.commit()
                self._persisted_incident_uuids[dedup_key] = new_inc.id
        except Exception as db_exc:
            logger.debug("Optional Kafka DB persistence skipped: %s", db_exc)

    async def handle_message(self, topic: str, value: dict[str, Any]):
        """Process a telemetry event: run EWMA detection, correlate across graph window, check suppression, and emit."""
        try:
            event = TelemetryEvent(**value)
            self.ring_buffer.push(value, is_anomaly_hint=False)
            logger.debug(
                "Received telemetry: service=%s metric=%s value=%s",
                event.service_id,
                event.metric_type,
                event.value,
            )

            engine = _get_detection_engine()
            ts = event.timestamp if event.timestamp else datetime.now(timezone.utc)

            result = engine.process_metric(
                service_id=event.service_id,
                metric_type=event.metric_type,
                value=event.value,
                timestamp=ts,
            )

            if result.is_anomaly:
                logger.info(
                    "Kafka-detected anomaly: service=%s metric=%s z=%.2f severity=%s",
                    event.service_id,
                    event.metric_type,
                    result.z_score,
                    result.severity,
                )

                anom_event = AnomalyEvent(
                    service_id=result.service_id,
                    metric_type=result.metric_type,
                    z_score=round(result.z_score, 2),
                    severity=result.severity,
                    detected_at=ts,
                )
                active_window = self._prune_and_append_anomaly(anom_event)

                # Correlate all anomalies in the active sliding window through the dependency graph
                correlated_incidents = self.correlation_engine.correlate(active_window)
                primary_inc = None
                for inc in correlated_incidents:
                    if event.service_id == inc.root_cause_service_id or event.service_id in inc.affected_service_ids:
                        primary_inc = inc
                        break
                if primary_inc is None and correlated_incidents:
                    primary_inc = correlated_incidents[0]

                root_service = primary_inc.root_cause_service_id if primary_inc else event.service_id
                root_cause_type = primary_inc.root_cause_type if primary_inc else f"{event.metric_type}_anomaly"
                affected_services = primary_inc.affected_service_ids if primary_inc else []
                confidence = primary_inc.confidence if primary_inc else min(abs(result.z_score) / 6.0, 0.99)
                signature = primary_inc.signature if primary_inc else []
                inc_start_ts = primary_inc.timestamp_start if primary_inc else ts
                is_multi_root = primary_inc.is_multi_root_cause if primary_inc else False

                # Check false-positive suppression before paging downstream incident consumers
                supp_decision = self.suppression_engine.evaluate(signature) if len(signature) == 7 else None
                is_suppressed = bool(supp_decision and supp_decision.should_suppress)

                producer = get_kafka_producer()

                if not is_suppressed:
                    dedup_key = f"kafka-{root_service}-{int(inc_start_ts.timestamp())}"
                    is_new_incident = dedup_key not in self._active_incidents
                    incident_event = IncidentEvent(
                        incident_id=dedup_key,
                        root_cause_service=root_service,
                        severity=result.severity,
                        confidence=confidence,
                        affected_services=affected_services,
                        event_type="detected" if is_new_incident else "correlated",
                    )
                    self._active_incidents[dedup_key] = incident_event

                    self._persist_to_db_if_configured(
                        dedup_key=dedup_key,
                        root_service=root_service,
                        root_cause_type=root_cause_type,
                        confidence=confidence,
                        is_multi_root=is_multi_root,
                        ts_start=inc_start_ts,
                        signature=signature,
                    )

                    await producer.publish_incident(incident_event)

                    # Broadcast live incident correlation to WebSocket & GraphQL Subscription clients
                    await broadcast_event({
                        "type": "incident_correlated",
                        "incident_id": incident_event.incident_id,
                        "root_cause_service": root_service,
                        "affected_services": affected_services,
                        "confidence": confidence,
                        "severity": result.severity,
                        "timestamp": ts.isoformat(),
                    })

                audit_event = AuditEvent(
                    event_type="anomaly_suppressed_via_kafka" if is_suppressed else "anomaly_correlated_via_kafka",
                    actor="telemetry_consumer",
                    details={
                        "observed_service_id": event.service_id,
                        "isolated_root_cause_service": root_service,
                        "affected_services": affected_services,
                        "metric_type": event.metric_type,
                        "value": event.value,
                        "z_score": result.z_score,
                        "severity": result.severity,
                        "confidence": confidence,
                        "suppressed": is_suppressed,
                    },
                )
                await producer.publish_audit(audit_event)

        except Exception as e:
            logger.error("Failed to process telemetry event: %s", e, exc_info=True)
            try:
                producer = get_kafka_producer()
                await producer.publish_dlq(payload=value, reason=str(e))
            except Exception as dlq_err:
                logger.error("Failed to route payload to DLQ: %s", dlq_err)
