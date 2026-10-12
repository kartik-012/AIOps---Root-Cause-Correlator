"""Unit & determinism tests for Suppression Engine and pgvector evaluation (Fix #2)."""

import os
import subprocess
import sys
from unittest.mock import MagicMock
import uuid

from app.engines.suppression_engine import SuppressionEngine, build_signature


def test_suppression_matching_false_positive():
    engine = SuppressionEngine(similarity_threshold=0.90)

    # Register daily batch job signature: hour_bucket=0 (midnight), day=6 (Sunday), service=batch-worker, metric=cpu, z=3.5
    batch_sig = build_signature(0, 6, "batch-worker", "cpu_usage", 3.5, depth=1.0, speed=10.0)
    engine.register_false_positive("past-inc-1", batch_sig, "weekly_batch_job")

    # Ingest candidate signature with identical service and metric at same Sunday midnight window
    candidate_sig = build_signature(0, 6, "batch-worker", "cpu_usage", 3.6, depth=1.0, speed=10.0)
    decision = engine.evaluate(candidate_sig)

    assert decision.should_suppress is True
    assert decision.similarity_score >= 0.90
    assert decision.matched_incident_id == "past-inc-1"
    assert decision.matched_tag == "weekly_batch_job"


def test_suppression_real_incident_not_suppressed():
    engine = SuppressionEngine(similarity_threshold=0.90)

    # Register daily batch job signature
    batch_sig = build_signature(0, 6, "batch-worker", "cpu_usage", 3.5, depth=1.0, speed=10.0)
    engine.register_false_positive("past-inc-1", batch_sig, "weekly_batch_job")

    # Ingest totally different signature: Monday 2 PM, payment-service database connection exhaustion, deep cascade
    outage_sig = build_signature(2, 0, "payment-service", "connection_pool", 5.8, depth=4.0, speed=2.0)
    decision = engine.evaluate(outage_sig)

    assert decision.should_suppress is False
    assert decision.similarity_score < 0.50  # Centered [-1, 1]^7 space separates orthogonal patterns cleanly


def test_build_signature_is_pythonhashseed_invariant():
    """Verify build_signature produces identical vectors across different PYTHONHASHSEED processes."""
    code = (
        "from app.engines.suppression_engine import build_signature; "
        "print(build_signature(1, 2, 'payment-service', 'db_connection_exhaustion', 5.4, 3.0, 4.5))"
    )
    env1 = {**os.environ, "PYTHONHASHSEED": "1"}
    env2 = {**os.environ, "PYTHONHASHSEED": "429496729"}

    out1 = subprocess.check_output([sys.executable, "-c", code], env=env1, text=True).strip()
    out2 = subprocess.check_output([sys.executable, "-c", code], env=env2, text=True).strip()

    assert out1 == out2
    vec = eval(out1)
    assert len(vec) == 7
    assert all(-1.0 <= x <= 1.0 for x in vec)


def test_evaluate_pgvector_sql_query_path():
    """Verify evaluate() queries PostgreSQL pgvector cosine_distance first when db session is provided."""
    engine = SuppressionEngine(similarity_threshold=0.90)
    sig = build_signature(0, 6, "batch-worker", "cpu_usage", 3.5, depth=1.0, speed=10.0)

    fake_incident = MagicMock()
    fake_incident.id = uuid.uuid4()
    fake_incident.learned_pattern_tag = "pgvector_batch_noise"
    fake_incident.root_cause_type = "cpu_spike"

    mock_db = MagicMock()
    # Simulate pgvector returning cosine_distance = 0.03 (so cosine similarity = 0.97)
    mock_db.execute.return_value.first.return_value = (fake_incident, 0.03)

    decision = engine.evaluate(sig, db=mock_db)

    assert decision.should_suppress is True
    assert decision.similarity_score == 0.97
    assert decision.matched_incident_id == str(fake_incident.id)
    assert decision.matched_tag == "pgvector_batch_noise"
    assert decision.evaluation_backend == "pgvector_sql"
