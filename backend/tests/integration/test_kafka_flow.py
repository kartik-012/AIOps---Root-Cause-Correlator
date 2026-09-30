"""Integration tests for Kafka telemetry → detection → incident flow.

Tests the full pipeline: telemetry event consumed from Kafka → fed into
DetectionEngine → anomaly detected → incident event published back to Kafka.
Uses mocks for Kafka transport but exercises real DetectionEngine logic.
"""

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import AsyncMock, patch

from app.kafka.events import TelemetryEvent, IncidentEvent
from app.kafka.consumers.telemetry_consumer import TelemetryConsumer


@pytest.mark.asyncio
async def test_telemetry_consumer_detects_anomaly_and_publishes_incident():
    """Burn in normal values, then send a spike. Consumer should publish an incident event."""
    consumer = TelemetryConsumer()

    t0 = datetime(2026, 10, 1, 10, 0, 0, tzinfo=timezone.utc)

    mock_producer = AsyncMock()
    mock_producer.publish_incident = AsyncMock()
    mock_producer.publish_audit = AsyncMock()

    with patch("app.kafka.consumers.telemetry_consumer.get_kafka_producer", return_value=mock_producer):
        # Burn in: send 5 normal values to establish EWMA baseline
        for i in range(5):
            normal_event = {
                "service_id": "payment-service",
                "metric_type": "connection_pool",
                "value": 20.0 + (i * 0.5),
                "timestamp": (t0 + timedelta(seconds=i * 10)).isoformat(),
            }
            await consumer.handle_message("service.telemetry", normal_event)

        # No incidents should have been published during burn-in
        assert mock_producer.publish_incident.call_count == 0

        # Now send a catastrophic spike
        spike_event = {
            "service_id": "payment-service",
            "metric_type": "connection_pool",
            "value": 350.0,  # Massive spike
            "timestamp": (t0 + timedelta(seconds=60)).isoformat(),
        }
        await consumer.handle_message("service.telemetry", spike_event)

        # An incident event should have been published
        assert mock_producer.publish_incident.call_count == 1

        incident_call = mock_producer.publish_incident.call_args[0][0]
        assert isinstance(incident_call, IncidentEvent)
        assert incident_call.root_cause_service == "payment-service"
        assert incident_call.event_type == "detected"
        assert incident_call.confidence > 0.5

        # Audit event should also have been published
        assert mock_producer.publish_audit.call_count == 1


@pytest.mark.asyncio
async def test_telemetry_consumer_no_anomaly_for_normal_values():
    """Normal values should not trigger any incident publication."""
    consumer = TelemetryConsumer()

    mock_producer = AsyncMock()
    mock_producer.publish_incident = AsyncMock()
    mock_producer.publish_audit = AsyncMock()

    with patch("app.kafka.consumers.telemetry_consumer.get_kafka_producer", return_value=mock_producer):
        t0 = datetime(2026, 10, 1, 11, 0, 0, tzinfo=timezone.utc)

        for i in range(10):
            event = {
                "service_id": "order-service",
                "metric_type": "latency_ms",
                "value": 45.0 + (i * 0.2),  # Very small drift — normal
                "timestamp": (t0 + timedelta(seconds=i * 5)).isoformat(),
            }
            await consumer.handle_message("service.telemetry", event)

        # No anomalies, no incidents
        assert mock_producer.publish_incident.call_count == 0


@pytest.mark.asyncio
async def test_telemetry_consumer_handles_malformed_event():
    """Malformed events should be routed to Dead Letter Queue (DLQ) without crashing."""
    consumer = TelemetryConsumer()
    mock_producer = AsyncMock()
    mock_producer.publish_dlq = AsyncMock()

    with patch("app.kafka.consumers.telemetry_consumer.get_kafka_producer", return_value=mock_producer):
        bad_event = {"foo": "bar"}
        await consumer.handle_message("service.telemetry", bad_event)
        mock_producer.publish_dlq.assert_called_once()
        args, kwargs = mock_producer.publish_dlq.call_args
        assert kwargs["payload"] == bad_event


@pytest.mark.asyncio
async def test_event_serialization_roundtrip():
    """TelemetryEvent can be serialized to dict and back."""
    original = TelemetryEvent(
        service_id="auth-service",
        metric_type="cpu_usage",
        value=78.5,
        trace_id="trace-abc-123",
    )

    data = original.model_dump()
    restored = TelemetryEvent(**{k: v if k != "timestamp" else v.isoformat() if hasattr(v, 'isoformat') else v for k, v in data.items()})

    assert restored.service_id == original.service_id
    assert restored.metric_type == original.metric_type
    assert restored.value == original.value
    assert restored.trace_id == original.trace_id
