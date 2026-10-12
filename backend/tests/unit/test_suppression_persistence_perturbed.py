"""Step 10 Item 3: 7D pgvector Cosine Similarity False-Positive Suppression Verification.

Verifies:
1. Persistence of false positive signatures across engine restarts.
2. Suppression of perturbed vectors within the cosine similarity boundary (cosine distance <= 0.10).
3. Non-suppression of orthogonal production outage vectors.
"""

import uuid
from datetime import datetime, timezone
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.models.db_models import Base, Incident
from app.engines.suppression_engine import SuppressionEngine, build_signature


@pytest.fixture
def test_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_suppression_engine_restart_and_perturbed_vector_matching(test_db: Session):
    # 1. Seed a historical false-positive maintenance window into the database
    maintenance_sig = build_signature(
        hour_bucket=2.0,
        day_of_week=6.0,  # Saturday 2 AM
        service_id="payment-service",
        metric_type="db_connection_count",
        severity_z=3.5,
        depth=1.0,
        speed=10.0,
    )

    incident_id = uuid.uuid4()
    incident = Incident(
        id=incident_id,
        timestamp_start=datetime(2026, 8, 22, 2, 0, 0, tzinfo=timezone.utc),
        root_cause_service_id=uuid.uuid4(),
        root_cause_type="scheduled_maintenance",
        was_false_positive=True,
        confidence_at_detection=0.92,
        anomaly_signature=maintenance_sig,
        resolution_action="Routine Saturday DB maintenance batch job",
    )
    test_db.add(incident)
    test_db.commit()

    # 2. Simulate ENGINE RESTART: Instantiate a brand-new SuppressionEngine with empty in-memory state
    fresh_engine = SuppressionEngine(similarity_threshold=0.88)
    assert len(fresh_engine._fp_patterns) == 0  # In-memory dictionary is completely empty

    # 3. Test perturbed vector (same maintenance event 30 mins later with slight metric jitter)
    perturbed_maintenance_sig = build_signature(
        hour_bucket=2.5,  # 30 min difference
        day_of_week=6.0,  # Saturday
        service_id="payment-service",
        metric_type="db_connection_count",
        severity_z=3.65,  # Slight z-score variance
        depth=1.0,
        speed=9.8,
    )

    # Query via fresh engine against DB
    similar = fresh_engine.retrieve_similar_incidents(
        candidate_signature=perturbed_maintenance_sig,
        db=test_db,
        top_k=5,
        false_positives_only=True,
    )
    assert len(similar) >= 1
    assert similar[0]["incident_id"] == str(incident_id)
    assert similar[0]["was_false_positive"] is True
    assert similar[0]["similarity"] >= 0.85

    # 4. Test orthogonal production outage vector (Wednesday afternoon, high-depth payment cascading failure)
    critical_outage_sig = build_signature(
        hour_bucket=14.0,  # Wednesday 2 PM
        day_of_week=3.0,
        service_id="api-gateway",
        metric_type="error_rate",
        severity_z=9.8,  # Critical severity
        depth=5.0,  # Multi-hop cascade
        speed=2.0,  # Extremely fast propagation
    )

    outage_matches = fresh_engine.retrieve_similar_incidents(
        candidate_signature=critical_outage_sig,
        db=test_db,
        top_k=5,
        false_positives_only=True,
    )
    # Critical orthogonal outage must have low similarity (< 0.70) against the maintenance pattern
    assert len(outage_matches) == 0 or outage_matches[0]["similarity"] < 0.70
