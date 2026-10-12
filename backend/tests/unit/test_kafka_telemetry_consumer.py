"""Unit tests for Kafka TelemetryConsumer — End-to-end EWMA detection, graph root-cause correlation, and suppression."""

from datetime import datetime, timezone, timedelta
import pytest

from app.kafka.consumers.telemetry_consumer import TelemetryConsumer, _get_detection_engine
from app.engines.suppression_engine import SuppressionEngine, build_signature
import app.kafka.consumers.telemetry_consumer as tc_module


class DummyProducer:
    def __init__(self):
        self.incidents = []
        self.audits = []
        self.dlq = []

    async def publish_incident(self, event):
        self.incidents.append(event)

    async def publish_audit(self, event):
        self.audits.append(event)

    async def publish_dlq(self, payload, reason):
        self.dlq.append((payload, reason))


@pytest.mark.asyncio
async def test_telemetry_consumer_correlates_cascade_to_upstream_root_cause(monkeypatch):
    """Verify Gap #6 verification method: publishing 3 cascading Kafka events
    (payment-service -> order-service -> api-gateway) results in 1 correlated incident
    persisted to the database with 'payment-service' isolated as the root cause.
    """
    from sqlalchemy import create_engine, select, func
    from sqlalchemy.orm import sessionmaker
    from app.models.db_models import Base, Incident

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    dummy_producer = DummyProducer()
    monkeypatch.setattr(tc_module, "get_kafka_producer", lambda: dummy_producer)

    det_engine = _get_detection_engine()
    det_engine.reset_state()

    consumer = TelemetryConsumer(
        correlation_window_seconds=60.0,
        db_session_factory=SessionLocal,
    )
    t0 = datetime(2026, 10, 12, 14, 0, 0, tzinfo=timezone.utc)

    # Warm up EWMA baselines for payment-service, order-service, and api-gateway
    for svc in ("payment-service", "order-service", "api-gateway"):
        for i in range(5):
            await consumer.handle_message(
                "service.telemetry",
                {
                    "service_id": svc,
                    "metric_type": "latency_ms",
                    "value": 50.0 + (1.0 if i % 2 == 0 else -1.0),
                    "timestamp": (t0 - timedelta(seconds=(5 - i) * 10)).isoformat(),
                },
            )

    assert len(dummy_producer.incidents) == 0

    # 1. Root fault on payment-service at t0
    await consumer.handle_message(
        "service.telemetry",
        {
            "service_id": "payment-service",
            "metric_type": "latency_ms",
            "value": 650.0,
            "timestamp": t0.isoformat(),
        },
    )
    # 2. Cascade to order-service at t0 + 5s
    await consumer.handle_message(
        "service.telemetry",
        {
            "service_id": "order-service",
            "metric_type": "latency_ms",
            "value": 420.0,
            "timestamp": (t0 + timedelta(seconds=5)).isoformat(),
        },
    )
    # 3. Cascade to api-gateway at t0 + 10s
    await consumer.handle_message(
        "service.telemetry",
        {
            "service_id": "api-gateway",
            "metric_type": "latency_ms",
            "value": 380.0,
            "timestamp": (t0 + timedelta(seconds=10)).isoformat(),
        },
    )

    # Assert 3 cascading Kafka events consolidated into 1 correlated incident in active window & DB
    correlated_incidents = consumer.get_correlated_incidents()
    assert len(correlated_incidents) == 1
    isolated = correlated_incidents[0]
    assert isolated.root_cause_service == "payment-service"
    assert "order-service" in isolated.affected_services
    assert "api-gateway" in isolated.affected_services

    with SessionLocal() as db:
        persisted_count = db.scalar(select(func.count()).select_from(Incident))
        assert persisted_count == 1



@pytest.mark.asyncio
async def test_telemetry_consumer_suppresses_known_false_positive_pattern(monkeypatch):
    """Verify TelemetryConsumer suppresses a known benign signature and logs anomaly_suppressed_via_kafka."""
    dummy_producer = DummyProducer()
    monkeypatch.setattr(tc_module, "get_kafka_producer", lambda: dummy_producer)

    det_engine = _get_detection_engine()
    det_engine.reset_state()

    t0 = datetime(2026, 10, 12, 14, 0, 0, tzinfo=timezone.utc)
    supp = SuppressionEngine(similarity_threshold=0.85)
    supp.register_false_positive(
        "fp-kafka-1",
        build_signature(
            hour_bucket=float(t0.hour // 6),
            day_of_week=float(t0.weekday()),
            service_id="inventory-service",
            metric_type="cpu_usage",
            severity_z=3.2,
            depth=1.0,
            speed=10.0,
        ),
        tag="scheduled_inventory_reconciliation",
    )

    consumer = TelemetryConsumer(suppression_engine=supp, correlation_window_seconds=60.0)

    for i in range(6):
        await consumer.handle_message(
            "service.telemetry",
            {
                "service_id": "inventory-service",
                "metric_type": "cpu_usage",
                "value": 40.0 + (1.0 if i % 2 == 0 else -1.0),
                "timestamp": (t0 - timedelta(seconds=(6 - i) * 10)).isoformat(),
            },
        )

    # Inject mild ~3.2z CPU spike matching the scheduled reconciliation template
    await consumer.handle_message(
        "service.telemetry",
        {
            "service_id": "inventory-service",
            "metric_type": "cpu_usage",
            "value": 43.2,
            "timestamp": t0.isoformat(),
        },
    )

    # Should be suppressed: 0 IncidentEvents published, 1 AuditEvent with 'anomaly_suppressed_via_kafka'
    assert len(dummy_producer.incidents) == 0
    assert len(dummy_producer.audits) == 1
    assert dummy_producer.audits[0].event_type == "anomaly_suppressed_via_kafka"
    assert dummy_producer.audits[0].details["suppressed"] is True
