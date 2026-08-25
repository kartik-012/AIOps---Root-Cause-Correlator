"""Unit tests for Suppression Engine."""

import pytest
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
    assert decision.similarity_score < 0.90
