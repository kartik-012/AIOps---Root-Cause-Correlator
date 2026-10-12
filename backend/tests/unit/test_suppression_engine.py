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


def test_suppression_exact_metadata_filtering_on_service_and_metric():
    """Verify Step 6.3: exact metadata filtering on (service_id, metric_type) prevents cross-service false suppression."""
    engine = SuppressionEngine(similarity_threshold=0.85)
    sig = build_signature(0, 6, "batch-worker", "cpu_usage", 3.5, depth=1.0, speed=10.0)
    engine.register_false_positive(
        "fp-meta-1",
        sig,
        tag="nightly_batch_cpu",
        service_id="batch-worker",
        metric_type="cpu_usage",
    )

    # Matching metadata -> suppressed
    match_dec = engine.evaluate(sig, service_id="batch-worker", metric_type="cpu_usage")
    assert match_dec.should_suppress is True

    # Mismatched service metadata -> never suppressed even with identical vector
    mismatch_dec = engine.evaluate(sig, service_id="payment-service", metric_type="cpu_usage")
    assert mismatch_dec.should_suppress is False


def test_embedded_grpc_loopback_server_startup_and_shutdown():
    """Verify Step 5.5: start_embedded_grpc_server runs DiagnosticService in-process on local loopback."""
    from app.grpc_services.diagnostic_server import start_embedded_grpc_server

    srv = start_embedded_grpc_server(port=50059)
    try:
        assert srv is not None
        # Second call on already-bound port must detect active listener and return None cleanly
        assert start_embedded_grpc_server(port=50059) is None
    finally:
        if srv is not None:
            srv.stop(grace=0.5)


def test_cyclical_time_encoding_midnight_boundary_continuity():
    """Verify Differentiator #3: 23:55 Sunday and 00:05 Monday produce near-identical unit-circle
    temporal coordinates (cosine similarity > 0.99) via build_signature_from_timestamp.
    """
    from datetime import datetime, timezone
    from app.engines.suppression_engine import build_signature_from_timestamp

    t_2355 = datetime(2026, 10, 11, 23, 55, 0, tzinfo=timezone.utc)
    t_0005 = datetime(2026, 10, 12, 0, 5, 0, tzinfo=timezone.utc)
    t_1200 = datetime(2026, 10, 12, 12, 0, 0, tzinfo=timezone.utc)

    sig_2355 = build_signature_from_timestamp(t_2355, "batch-worker", "cpu_usage", 3.4)
    sig_0005 = build_signature_from_timestamp(t_0005, "batch-worker", "cpu_usage", 3.4)
    sig_1200 = build_signature_from_timestamp(t_1200, "batch-worker", "cpu_usage", 3.4)

    sim_midnight = SuppressionEngine.cosine_similarity(sig_2355, sig_0005)
    sim_noon = SuppressionEngine.cosine_similarity(sig_2355, sig_1200)

    assert sim_midnight > 0.99
    assert sim_noon < 0.50


def test_retrieve_similar_incidents_pgvector_and_db_fallback():
    """Verify Differentiator #3: retrieve_similar_incidents returns Top-K nearest historical incidents
    via pgvector SQL query path and falls back cleanly when running on SQLite.
    """
    from datetime import datetime, timezone
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models.db_models import Base, Service, Incident
    from app.engines.suppression_engine import build_signature_from_timestamp

    engine = SuppressionEngine(similarity_threshold=0.90)
    t0 = datetime(2026, 10, 12, 0, 5, 0, tzinfo=timezone.utc)
    sig_target = build_signature_from_timestamp(t0, "batch-worker", "cpu_usage", 3.5)

    # 1. Test pgvector_sql path with mocked DB session
    fake_inc = MagicMock()
    fake_inc.id = uuid.uuid4()
    fake_inc.root_cause_type = "cpu_usage"
    fake_inc.was_false_positive = True
    fake_inc.learned_pattern_tag = "midnight_etl_batch"

    mock_db = MagicMock()
    mock_db.execute.return_value.all.return_value = [(fake_inc, 0.02)]

    pg_matches = engine.retrieve_similar_incidents(sig_target, db=mock_db, top_k=3)
    assert len(pg_matches) == 1
    assert pg_matches[0]["similarity"] == 0.98
    assert pg_matches[0]["backend"] == "pgvector_sql"
    assert pg_matches[0]["learned_pattern_tag"] == "midnight_etl_batch"

    # 2. Test SQLite DB fallback path with real Incident rows
    sql_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(sql_engine)
    SessionLocal = sessionmaker(bind=sql_engine)

    with SessionLocal() as db:
        svc = Service(id=uuid.uuid4(), name="batch-worker", revenue_weight=4.0)
        db.add(svc)
        db.flush()

        inc_near = Incident(
            id=uuid.uuid4(),
            root_cause_service_id=svc.id,
            root_cause_type="cpu_usage",
            confidence_at_detection=0.88,
            was_false_positive=True,
            learned_pattern_tag="midnight_etl_batch",
            timestamp_start=t0,
            anomaly_signature=sig_target,
        )
        inc_far = Incident(
            id=uuid.uuid4(),
            root_cause_service_id=svc.id,
            root_cause_type="db_pool_exhaustion",
            confidence_at_detection=0.95,
            was_false_positive=False,
            timestamp_start=datetime(2026, 10, 12, 12, 0, 0, tzinfo=timezone.utc),
            anomaly_signature=build_signature_from_timestamp(
                datetime(2026, 10, 12, 12, 0, 0, tzinfo=timezone.utc),
                "payment-service",
                "db_pool_exhaustion",
                5.8,
                depth=4.0,
                speed=1.5,
            ),
        )
        db.add_all([inc_near, inc_far])
        db.commit()

        all_matches = engine.retrieve_similar_incidents(sig_target, db=db, top_k=2, false_positives_only=False)
        assert len(all_matches) == 2
        assert all_matches[0]["incident_id"] == str(inc_near.id)
        assert all_matches[0]["similarity"] == 1.0
        assert all_matches[0][" similarity" if " similarity" in all_matches[0] else "similarity"] > all_matches[1]["similarity"]


