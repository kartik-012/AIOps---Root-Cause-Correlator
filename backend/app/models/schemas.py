"""Pydantic v2 request/response schemas for all API endpoints."""

from __future__ import annotations

import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


# ---------------------------------------------------------------------------
# Service schemas
# ---------------------------------------------------------------------------

class ServiceOut(BaseModel):
    """Response schema for a service."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    revenue_weight: float
    created_at: datetime


class ServiceCreate(BaseModel):
    """Request schema to register a new service."""
    name: str
    revenue_weight: float = 1.0


class DependencyCreate(BaseModel):
    """Request schema to add a dependency edge."""
    from_service_id: uuid.UUID
    to_service_id: uuid.UUID


class GraphNode(BaseModel):
    """A node in the dependency graph response."""
    id: uuid.UUID
    name: str
    revenue_weight: float = 1.0


class GraphEdge(BaseModel):
    """An edge in the dependency graph response."""
    source: uuid.UUID = Field(alias="from")
    target: uuid.UUID = Field(alias="to")

    model_config = ConfigDict(populate_by_name=True)


class GraphResponse(BaseModel):
    """Full dependency graph."""
    nodes: list[GraphNode]
    edges: list[GraphEdge]


# ---------------------------------------------------------------------------
# Metric / Detection schemas
# ---------------------------------------------------------------------------

class MetricIngest(BaseModel):
    """Request to ingest a raw metric data point."""
    service_id: uuid.UUID
    metric_type: str
    value: float
    recorded_at: datetime | None = None


class MetricIngestResponse(BaseModel):
    """Response after ingesting a metric."""
    status: str = "recorded"
    anomaly_detected: bool = False
    anomaly_id: uuid.UUID | None = None
    z_score: float | None = None
    severity: str | None = None


class AnomalyOut(BaseModel):
    """Response schema for a detected anomaly."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    service_id: uuid.UUID
    metric_type: str
    z_score: float
    severity: str
    detected_at: datetime
    incident_id: uuid.UUID | None = None


# ---------------------------------------------------------------------------
# Correlation / Incident schemas
# ---------------------------------------------------------------------------

class AffectedServiceOut(BaseModel):
    """A service affected by an incident, with propagation order."""
    model_config = ConfigDict(from_attributes=True)

    service_id: uuid.UUID
    service_name: str | None = None
    propagation_order: int
    affected_at: datetime


class IncidentSummary(BaseModel):
    """Summary of a correlated incident (returned in lists)."""
    incident_id: uuid.UUID
    root_cause_service: str | None = None
    root_cause_service_id: uuid.UUID | None = None
    root_cause_type: str | None = None
    confidence: float | None = None
    affected_services: list[str] = []
    is_multi_root_cause: bool = False
    timestamp_start: datetime | None = None


class CorrelationRunResponse(BaseModel):
    """Response from POST /correlation/run."""
    incidents: list[IncidentSummary]


class IncidentDetail(BaseModel):
    """Full incident detail for GET /correlation/incidents/{id}."""
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    timestamp_start: datetime
    timestamp_end: datetime | None = None
    root_cause_service_id: uuid.UUID | None = None
    root_cause_service_name: str | None = None
    root_cause_type: str | None = None
    confidence_at_detection: float | None = None
    is_multi_root_cause: bool = False
    was_false_positive: bool = False
    anomaly_signature: list[float] | None = None
    affected_services: list[AffectedServiceOut] = []
    anomalies: list[AnomalyOut] = []


# ---------------------------------------------------------------------------
# Suppression schemas
# ---------------------------------------------------------------------------

class SuppressionCheckRequest(BaseModel):
    """Request to check an anomaly against known false positives."""
    anomaly_signature: list[float] = Field(min_length=7, max_length=7)


class SuppressionCheckResponse(BaseModel):
    """Response from suppression check."""
    suppress: bool = False
    matched_incident_id: uuid.UUID | None = None
    similarity: float = 0.0


class MarkFalsePositiveResponse(BaseModel):
    """Response after marking an incident as false positive."""
    status: str = "marked"
    incident_id: uuid.UUID


# ---------------------------------------------------------------------------
# Prediction schemas
# ---------------------------------------------------------------------------

class BlastRadiusPredictionOut(BaseModel):
    """A single blast radius prediction for a downstream service."""
    service: str
    service_id: uuid.UUID | None = None
    eta_seconds: int
    confidence: float


class BlastRadiusResponse(BaseModel):
    """Response for blast radius prediction."""
    predictions: list[BlastRadiusPredictionOut]


# ---------------------------------------------------------------------------
# Counterfactual schemas
# ---------------------------------------------------------------------------

class ModifiedParameter(BaseModel):
    """A parameter modification for what-if simulation."""
    service: str
    metric: str
    capped_at: float


class CounterfactualRequest(BaseModel):
    """Request to run a counterfactual simulation."""
    incident_id: uuid.UUID
    modified_parameter: ModifiedParameter


class CounterfactualResponse(BaseModel):
    """Response from counterfactual simulation."""
    would_cascade: bool
    original_affected_services: list[str]
    simulated_affected_services: list[str]


# ---------------------------------------------------------------------------
# Impact schemas
# ---------------------------------------------------------------------------

class ImpactResponse(BaseModel):
    """Business impact score for an incident."""
    impact_score: float
    severity: str
    revenue_weighted: bool = True


# ---------------------------------------------------------------------------
# Explain schemas
# ---------------------------------------------------------------------------

class ExplainResponse(BaseModel):
    """Structured explanation of an incident."""
    summary: str
    evidence: list[str]


# ---------------------------------------------------------------------------
# Runbook schemas
# ---------------------------------------------------------------------------

class RunbookResponse(BaseModel):
    """Suggested runbook for a root cause type."""
    title: str
    severity: str
    suggested_action: str | None = None
    steps: list[str] = []
    prevention: str | None = None


class RunbookApproveResponse(BaseModel):
    """Response after approving a runbook."""
    status: str = "approved"
    incident_id: uuid.UUID


# ---------------------------------------------------------------------------
# Evaluation schemas
# ---------------------------------------------------------------------------

class EvaluationMetrics(BaseModel):
    """Metrics from running the full evaluation test suite."""
    top1_accuracy: float | None = None
    top3_accuracy: float | None = None
    multi_incident_separation_accuracy: float | None = None
    suppression_precision: float | None = None
    suppression_recall: float | None = None
    blast_radius_accuracy: float | None = None
    mean_detection_time_seconds: float | None = None
    total_scenarios: int = 0
    passed: int = 0
    failed: int = 0


# ---------------------------------------------------------------------------
# WebSocket event schemas
# ---------------------------------------------------------------------------

class WSEvent(BaseModel):
    """A WebSocket event pushed to the frontend."""
    type: str  # 'anomaly_detected', 'incident_correlated', 'blast_radius_updated'
    data: dict = {}
    timestamp: datetime | None = None
