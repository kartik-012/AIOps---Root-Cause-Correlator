"""Unit tests for Kafka events."""

import json
from datetime import datetime, timezone
from app.kafka.events import TelemetryEvent, IncidentEvent

def test_telemetry_event_serialization():
    dt = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
    event = TelemetryEvent(
        service_id="svc-123",
        metric_type="cpu",
        value=95.5,
        timestamp=dt
    )
    
    # Serialize to dict then json
    data = event.model_dump()
    assert data["service_id"] == "svc-123"
    assert data["metric_type"] == "cpu"
    assert data["value"] == 95.5
    
    # Test JSON serialization compatibility
    json_str = json.dumps(data, default=str)
    assert "svc-123" in json_str

def test_incident_event_default_values():
    event = IncidentEvent(
        incident_id="inc-1",
        root_cause_service="svc-1",
        severity="high",
        confidence=0.85
    )
    
    assert event.event_type == "detected"
    assert event.affected_services == []
