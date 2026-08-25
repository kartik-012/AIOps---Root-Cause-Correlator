"""Database connectivity and schema verification test."""

import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import inspect, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.dependencies import get_session_factory
from app.models.db_models import (
    Base,
    Service,
    ServiceDependency,
    MetricRaw,
    Anomaly,
    Incident,
    IncidentAffectedService,
    Suppression,
    BlastRadiusPrediction,
    RunbookSuggestion,
)


def test_database_connection_and_tables():
    """Verify all 9 tables exist in PostgreSQL."""
    settings = get_settings()
    session_factory = get_session_factory(settings)
    engine = session_factory.kw["bind"]

    inspector = inspect(engine)
    tables = inspector.get_table_names()

    expected_tables = {
        "services",
        "service_dependencies",
        "metrics_raw",
        "anomalies",
        "incidents",
        "incident_affected_services",
        "suppressions",
        "blast_radius_predictions",
        "runbook_suggestions",
        "alembic_version",
    }

    for expected in expected_tables:
        assert expected in tables, f"Expected table '{expected}' not found in database. Existing: {tables}"


def test_crud_and_vector_column():
    """Verify insert and query across services, incidents, vector(7) signature."""
    settings = get_settings()
    session_factory = get_session_factory(settings)
    
    with session_factory() as session:
        # Create test services
        svc_a = Service(name=f"test-auth-{uuid.uuid4().hex[:6]}", revenue_weight=5.0)
        svc_b = Service(name=f"test-pay-{uuid.uuid4().hex[:6]}", revenue_weight=8.0)
        session.add_all([svc_a, svc_b])
        session.commit()
        session.refresh(svc_a)
        session.refresh(svc_b)

        # Create dependency
        dep = ServiceDependency(from_service_id=svc_a.id, to_service_id=svc_b.id)
        session.add(dep)
        session.commit()

        # Create incident with pgvector anomaly_signature (7-dim vector)
        sig = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7]
        incident = Incident(
            timestamp_start=datetime.now(timezone.utc),
            root_cause_service_id=svc_b.id,
            root_cause_type="db_connection_exhaustion",
            confidence_at_detection=0.92,
            is_multi_root_cause=False,
            was_false_positive=False,
            anomaly_signature=sig,
        )
        session.add(incident)
        session.commit()
        session.refresh(incident)

        assert incident.id is not None
        assert incident.root_cause_service_id == svc_b.id

        # Verify pgvector distance calculation works in SQL
        res = session.execute(
            text("SELECT id, anomaly_signature <=> :vec AS distance FROM incidents WHERE id = :id"),
            {"vec": str(sig), "id": str(incident.id)}
        ).fetchone()

        assert res is not None
        assert res[1] < 1e-5, f"Vector distance should be 0 for exact match, got {res[1]}"

        # Cleanup test data
        session.delete(incident)
        session.delete(dep)
        session.delete(svc_a)
        session.delete(svc_b)
        session.commit()
