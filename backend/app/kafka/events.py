"""Kafka event models."""

from typing import Optional, Any
from datetime import datetime, timezone
from pydantic import BaseModel, Field

class BaseEvent(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
    model_config = {
        "populate_by_name": True,
    }

class TelemetryEvent(BaseEvent):
    service_id: str
    metric_type: str
    value: float
    trace_id: Optional[str] = None

class IncidentEvent(BaseEvent):
    incident_id: str
    root_cause_service: str
    severity: str
    confidence: float
    affected_services: list[str] = Field(default_factory=list)
    event_type: str = "detected" # e.g., "detected", "updated", "resolved"

class RemediationEvent(BaseEvent):
    incident_id: str
    action: str
    status: str
    approved_by: Optional[str] = None

class AuditEvent(BaseEvent):
    event_type: str
    actor: str
    details: dict[str, Any] = Field(default_factory=dict)
