"""SQLAlchemy ORM models for AIOps Root Cause Correlator.

Nine tables matching the schema defined in 02-postgres-schema.md:
services, service_dependencies, metrics_raw, anomalies, incidents,
incident_affected_services, suppressions, blast_radius_predictions,
runbook_suggestions.
"""

import uuid
from datetime import datetime, timezone

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy models."""
    pass


# ---------------------------------------------------------------------------
# 1. services — Service Registry
# ---------------------------------------------------------------------------

class Service(Base):
    """A registered microservice in the dependency graph."""

    __tablename__ = "services"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    revenue_weight: Mapped[float] = mapped_column(Float, nullable=False, default=1.0)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    # Relationships
    anomalies: Mapped[list["Anomaly"]] = relationship(back_populates="service")
    metrics: Mapped[list["MetricRaw"]] = relationship(back_populates="service")


# ---------------------------------------------------------------------------
# 2. service_dependencies — Directed edges in the dependency graph
# ---------------------------------------------------------------------------

class ServiceDependency(Base):
    """A directed dependency edge: from_service depends on to_service."""

    __tablename__ = "service_dependencies"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    from_service_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("services.id", ondelete="CASCADE"), nullable=False
    )
    to_service_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("services.id", ondelete="CASCADE"), nullable=False
    )

    __table_args__ = (
        UniqueConstraint("from_service_id", "to_service_id"),
    )

    from_service: Mapped["Service"] = relationship(foreign_keys=[from_service_id])
    to_service: Mapped["Service"] = relationship(foreign_keys=[to_service_id])


# ---------------------------------------------------------------------------
# 3. metrics_raw — Time-series telemetry
# ---------------------------------------------------------------------------

class MetricRaw(Base):
    """A single raw metric data point for a service."""

    __tablename__ = "metrics_raw"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    service_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("services.id"), nullable=False
    )
    metric_type: Mapped[str] = mapped_column(String(50), nullable=False)
    value: Mapped[float] = mapped_column(Float, nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("idx_metrics_service_time", "service_id", recorded_at.desc()),
        Index("idx_metrics_type", "metric_type"),
    )

    service: Mapped["Service"] = relationship(back_populates="metrics")


# ---------------------------------------------------------------------------
# 4. incidents — Correlated incident records
# ---------------------------------------------------------------------------

class Incident(Base):
    """A correlated incident linking anomalies to a root cause."""

    __tablename__ = "incidents"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    timestamp_start: Mapped[datetime] = mapped_column(nullable=False)
    timestamp_end: Mapped[datetime | None] = mapped_column(nullable=True)
    root_cause_service_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("services.id"), nullable=True
    )
    root_cause_type: Mapped[str | None] = mapped_column(String(100), nullable=True)
    confidence_at_detection: Mapped[float | None] = mapped_column(Float, nullable=True)
    is_multi_root_cause: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    resolution_action: Mapped[str | None] = mapped_column(Text, nullable=True)
    was_false_positive: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    learned_pattern_tag: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )
    anomaly_signature = mapped_column(Vector(7), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    __table_args__ = (
        Index("idx_incidents_root_cause_type", "root_cause_type"),
        Index("idx_incidents_false_positive", "was_false_positive"),
    )

    # Relationships
    root_cause_service: Mapped["Service"] = relationship(
        foreign_keys=[root_cause_service_id]
    )
    anomalies: Mapped[list["Anomaly"]] = relationship(back_populates="incident")
    affected_services: Mapped[list["IncidentAffectedService"]] = relationship(
        back_populates="incident"
    )
    blast_radius_predictions: Mapped[list["BlastRadiusPrediction"]] = relationship(
        back_populates="incident"
    )
    runbook_suggestions: Mapped[list["RunbookSuggestion"]] = relationship(
        back_populates="incident"
    )


# ---------------------------------------------------------------------------
# 5. anomalies — Detected anomaly events
# ---------------------------------------------------------------------------

class Anomaly(Base):
    """A detected anomaly on a specific service and metric."""

    __tablename__ = "anomalies"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("services.id"), nullable=False
    )
    metric_type: Mapped[str] = mapped_column(String(50), nullable=False)
    z_score: Mapped[float] = mapped_column(Float, nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    detected_at: Mapped[datetime] = mapped_column(
        nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    incident_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("incidents.id"), nullable=True
    )

    __table_args__ = (
        Index("idx_anomalies_detected_at", detected_at.desc()),
        Index("idx_anomalies_incident", "incident_id"),
    )

    service: Mapped["Service"] = relationship(back_populates="anomalies")
    incident: Mapped["Incident | None"] = relationship(back_populates="anomalies")


# ---------------------------------------------------------------------------
# 6. incident_affected_services — Propagation order (many-to-many with order)
# ---------------------------------------------------------------------------

class IncidentAffectedService(Base):
    """Tracks which services were affected by an incident and in what order."""

    __tablename__ = "incident_affected_services"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("incidents.id", ondelete="CASCADE"), nullable=False
    )
    service_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("services.id"), nullable=False
    )
    propagation_order: Mapped[int] = mapped_column(Integer, nullable=False)
    affected_at: Mapped[datetime] = mapped_column(nullable=False)

    __table_args__ = (
        Index("idx_ias_incident", "incident_id", "propagation_order"),
    )

    incident: Mapped["Incident"] = relationship(back_populates="affected_services")
    service: Mapped["Service"] = relationship()


# ---------------------------------------------------------------------------
# 7. suppressions — False-positive suppression log
# ---------------------------------------------------------------------------

class Suppression(Base):
    """Log entry for a suppressed anomaly matched to a past false positive."""

    __tablename__ = "suppressions"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    triggering_anomaly_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("anomalies.id"), nullable=False
    )
    matched_incident_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("incidents.id"), nullable=False
    )
    similarity_score: Mapped[float] = mapped_column(Float, nullable=False)
    suppressed_at: Mapped[datetime] = mapped_column(
        nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    triggering_anomaly: Mapped["Anomaly"] = relationship()
    matched_incident: Mapped["Incident"] = relationship()


# ---------------------------------------------------------------------------
# 8. blast_radius_predictions — Prediction engine output
# ---------------------------------------------------------------------------

class BlastRadiusPrediction(Base):
    """A predicted service impact from a blast radius analysis."""

    __tablename__ = "blast_radius_predictions"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("incidents.id"), nullable=False
    )
    predicted_service_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("services.id"), nullable=False
    )
    predicted_eta_seconds: Mapped[int] = mapped_column(Integer, nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    was_correct: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    predicted_at: Mapped[datetime] = mapped_column(
        nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    incident: Mapped["Incident"] = relationship(back_populates="blast_radius_predictions")
    predicted_service: Mapped["Service"] = relationship()


# ---------------------------------------------------------------------------
# 9. runbook_suggestions — Remediation log
# ---------------------------------------------------------------------------

class RunbookSuggestion(Base):
    """A suggested remediation action linked to an incident."""

    __tablename__ = "runbook_suggestions"

    id: Mapped[uuid.UUID] = mapped_column(
        primary_key=True, default=uuid.uuid4
    )
    incident_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("incidents.id"), nullable=False
    )
    root_cause_type: Mapped[str] = mapped_column(String(100), nullable=False)
    suggested_action: Mapped[str] = mapped_column(Text, nullable=False)
    was_approved: Mapped[bool | None] = mapped_column(Boolean, nullable=True)
    suggested_at: Mapped[datetime] = mapped_column(
        nullable=False, default=lambda: datetime.now(timezone.utc)
    )

    incident: Mapped["Incident"] = relationship(back_populates="runbook_suggestions")
