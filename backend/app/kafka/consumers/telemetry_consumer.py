"""Telemetry Kafka consumer — feeds incoming telemetry events into the DetectionEngine.

Subscribes to the service.telemetry topic. When an anomaly is detected,
publishes an IncidentEvent to the incident.detected topic and broadcasts
a WebSocket notification.
"""

import logging
from datetime import datetime, timezone

from ..consumer import BaseKafkaConsumer
from ..config import get_kafka_config
from ..events import TelemetryEvent, IncidentEvent, AuditEvent
from ..producer import get_kafka_producer

logger = logging.getLogger(__name__)

# Shared DetectionEngine instance — same singleton used by the REST API
# Import lazily to avoid circular imports at module level
_engine = None


def _get_detection_engine():
    """Get or create the shared DetectionEngine singleton."""
    global _engine
    if _engine is None:
        from ...engines.detection_engine import DetectionEngine
        _engine = DetectionEngine(alpha=0.3, base_threshold=2.5, min_samples=3)
    return _engine


class TelemetryConsumer(BaseKafkaConsumer):
    """Consumes telemetry events from Kafka and runs anomaly detection."""

    def __init__(self):
        config = get_kafka_config()
        super().__init__(
            topics=[config.TOPIC_TELEMETRY],
            group_id=config.CG_TELEMETRY,
            config=config,
        )

    async def handle_message(self, topic: str, value: dict):
        """Process a telemetry event: run detection, publish incident if anomaly found."""
        try:
            event = TelemetryEvent(**value)
            logger.debug(f"Received telemetry: service={event.service_id} metric={event.metric_type} value={event.value}")

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
                    f"Kafka-detected anomaly: service={event.service_id} "
                    f"metric={event.metric_type} z={result.z_score:.2f} severity={result.severity}"
                )

                # Publish incident event
                producer = get_kafka_producer()
                incident_event = IncidentEvent(
                    incident_id=f"kafka-{event.service_id}-{int(ts.timestamp())}",
                    root_cause_service=event.service_id,
                    severity=result.severity,
                    confidence=min(abs(result.z_score) / 6.0, 0.99),
                    event_type="detected",
                )
                await producer.publish_incident(incident_event)

                # Publish audit trail
                audit_event = AuditEvent(
                    event_type="anomaly_detected_via_kafka",
                    actor="telemetry_consumer",
                    details={
                        "service_id": event.service_id,
                        "metric_type": event.metric_type,
                        "value": event.value,
                        "z_score": result.z_score,
                        "severity": result.severity,
                        "ewma_mean": result.ewma_mean,
                        "ewma_std": result.ewma_std,
                    },
                )
                await producer.publish_audit(audit_event)

        except Exception as e:
            logger.error(f"Failed to process telemetry event: {e}", exc_info=True)
            try:
                producer = get_kafka_producer()
                await producer.publish_dlq(payload=value, reason=str(e))
            except Exception as dlq_err:
                logger.error(f"Failed to route payload to DLQ: {dlq_err}")
