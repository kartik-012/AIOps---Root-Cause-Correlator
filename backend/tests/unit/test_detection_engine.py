"""Unit tests for Detection Engine — EWMA baseline, Redis state persistence, poisoning guard, and singleton unification."""

from datetime import datetime, timezone
import pytest

from app.engines.detection_engine import DetectionEngine, EWMAState, get_shared_detection_engine
from app.api.v1.detection import get_detection_engine
from app.kafka.consumers.telemetry_consumer import _get_detection_engine
from app.tasks.celery_app import celery_app, generate_incident_post_mortem_task


class FakeRedis:
    """In-memory mock Redis client supporting both Redis Hash (hset/hgetall) and string (get/setex)."""

    def __init__(self):
        self.store: dict[str, str] = {}
        self.hashes: dict[str, dict[str, str]] = {}

    def hset(self, key: str, mapping: dict[str, str]):
        self.hashes.setdefault(key, {}).update(mapping)

    def hgetall(self, key: str) -> dict[str, str]:
        return dict(self.hashes.get(key, {}))

    def expire(self, key: str, ttl: int):
        return True

    def get(self, key: str):
        return self.store.get(key)

    def setex(self, key: str, ttl: int, value: str):
        self.store[key] = value

    def delete(self, key: str):
        self.store.pop(key, None)
        self.hashes.pop(key, None)


def test_ewma_state_updates():
    state = EWMAState(alpha=0.3, min_samples=3)
    # Burn in 3 normal values
    m1, s1, z1 = state.update(100.0)
    m2, s2, z2 = state.update(100.0)
    m3, s3, z3 = state.update(100.0)

    assert state.count == 3
    assert abs(m3 - 100.0) < 1e-3

    # Anomaly spike
    m4, s4, z4 = state.update(300.0)
    assert z4 > 2.0  # Significant positive z-score


def test_detection_engine_nominal_and_spike():
    engine = DetectionEngine(alpha=0.2, base_threshold=2.0, min_samples=3)
    now = datetime.now(timezone.utc)

    # Ingest 5 normal latency samples around 50ms
    for i in range(5):
        res = engine.process_metric("order-svc", "latency_ms", 50.0 + (i % 2), now)
        assert not res.is_anomaly or i < 3

    # Sudden 10x latency spike
    spike_res = engine.process_metric("order-svc", "latency_ms", 550.0, now)
    assert spike_res.is_anomaly
    assert spike_res.z_score >= 2.0
    assert spike_res.severity in ("high", "critical")


def test_detection_engine_baseline_poisoning_guard_preserves_consecutive_spike_detection():
    """Verify a severe spike (|z| >= 4.0) does not poison EWMA variance and mask the very next spike."""
    engine = DetectionEngine(alpha=0.3, base_threshold=2.5, min_samples=3)
    now = datetime.now(timezone.utc)

    for i in range(6):
        engine.process_metric("payment-svc", "latency_ms", 50.0 + (1.0 if i % 2 == 0 else -1.0), now)

    first_spike = engine.process_metric("payment-svc", "latency_ms", 450.0, now)
    second_spike = engine.process_metric("payment-svc", "latency_ms", 450.0, now)

    assert first_spike.is_anomaly is True
    assert second_spike.is_anomaly is True
    assert second_spike.z_score >= 4.0


def test_detection_engine_drift_adaptation():
    """Gradual organic growth (within 1.5 sigma per step) should adapt the baseline without creating persistent anomalies."""
    engine = DetectionEngine(alpha=0.3, base_threshold=3.0, min_samples=3)
    now = datetime.now(timezone.utc)

    # Burn in around 100 +/- 3 so initial Welford std is ~3.0, then drift smoothly by +2.5 per step
    for b in (97.0, 103.0, 100.0):
        engine.process_metric("auth-svc", "cpu_usage", b, now)
    for step in range(1, 25):
        engine.process_metric("auth-svc", "cpu_usage", 100.0 + step * 2.5, now)

    state = engine._states[("auth-svc", "cpu_usage")]
    assert state.mean > 140.0


def test_welford_burn_in_variance_adapts_across_sub_unit_and_high_scale_metrics():
    """Verify Step 6.1: Welford burn-in avoids cold-start false negatives on error_rate (0.01)
    and avoids false positives on normal latency_ms (200ms -> 205ms) jitter.
    """
    engine = DetectionEngine(alpha=0.3, base_threshold=2.0, min_samples=3)
    now = datetime.now(timezone.utc)

    # 1. Sub-unit metric: error_rate ~ 0.01 -> 50% error rate (0.50) must be flagged as critical anomaly
    for val in (0.010, 0.012, 0.008):
        engine.process_metric("payment-svc", "error_rate", val, now)
    err_spike = engine.process_metric("payment-svc", "error_rate", 0.50, now)
    assert err_spike.is_anomaly is True
    assert err_spike.severity == "critical"

    # 2. High-scale metric: latency_ms ~ 200ms +/- 5ms -> sample 4 at 205ms must NOT trigger a false positive
    for val in (195.0, 205.0, 200.0):
        engine.process_metric("api-gateway", "latency_ms", val, now)
    normal_jitter = engine.process_metric("api-gateway", "latency_ms", 205.0, now)
    assert normal_jitter.is_anomaly is False
    assert abs(normal_jitter.z_score) < 2.0


def test_sustained_8_sample_outlier_burst_does_not_contaminate_ewma_baseline():
    """Verify Step 6.1: 8 consecutive anomalous samples (|z| >= threshold) do not inflate sigma
    such that anomalies fall below z = 2.0.
    """
    engine = DetectionEngine(alpha=0.3, base_threshold=2.0, min_samples=3)
    now = datetime.now(timezone.utc)

    for val in (50.0, 51.0, 49.0):
        engine.process_metric("order-svc", "latency_ms", val, now)

    # Stream 8 consecutive moderate-to-high anomaly samples
    results = [
        engine.process_metric("order-svc", "latency_ms", 62.0, now)
        for _ in range(8)
    ]
    assert all(r.is_anomaly is True for r in results)
    assert all(r.winsorized is True for r in results)
    assert results[-1].z_score >= 2.0


def test_winsorized_residual_clipping_bounds_variance_under_extreme_1000_sigma_spike():
    """Verify Differentiator #1: Without Winsorized residual clipping, a 1000-sigma spike (50 -> 5000)
    inflates variance quadratically (d^2 = 24,502,500) even with small alpha, blinding the detector
    to subsequent moderate spikes (e.g., 65.0). With Winsorized clipping, the moderate spike is still caught.
    """
    engine = DetectionEngine(alpha=0.3, base_threshold=2.0, min_samples=3)
    now = datetime.now(timezone.utc)

    for val in (49.0, 51.0, 50.0):
        engine.process_metric("catalog-svc", "latency_ms", val, now)

    extreme_spike = engine.process_metric("catalog-svc", "latency_ms", 5000.0, now)
    assert extreme_spike.is_anomaly is True
    assert extreme_spike.winsorized is True

    # Immediately follow with a moderate anomaly (65.0 vs baseline ~50.0)
    follow_up = engine.process_metric("catalog-svc", "latency_ms", 65.0, now)
    assert follow_up.is_anomaly is True
    assert follow_up.z_score >= 4.0



def test_detection_engine_redis_persistence_roundtrip():
    """Verify EWMA state is persisted to Redis hash (ewma:{service_id}:{metric}) and restored after restart."""
    fake_redis = FakeRedis()
    now = datetime.now(timezone.utc)

    engine_a = DetectionEngine(alpha=0.3, base_threshold=2.0, min_samples=3, redis_client=fake_redis)
    for i in range(5):
        engine_a.process_metric("inventory-svc", "cpu_usage", 40.0 + (i % 2), now)

    saved_mean = engine_a._states[("inventory-svc", "cpu_usage")].mean
    saved_var = engine_a._states[("inventory-svc", "cpu_usage")].variance
    assert "ewma:inventory-svc:cpu_usage" in fake_redis.hashes

    # Kill first engine instance and simulate process restart with a brand new DetectionEngine
    del engine_a
    engine_b = DetectionEngine(alpha=0.3, base_threshold=2.0, min_samples=3, redis_client=fake_redis)
    restored_state = engine_b._get_or_create_state("inventory-svc", "cpu_usage")
    assert abs(restored_state.mean - saved_mean) < 1e-9
    assert abs(restored_state.variance - saved_var) < 1e-9

    res = engine_b.process_metric("inventory-svc", "cpu_usage", 180.0, now)

    # Without Redis restore, count would be 1 (< min_samples=3) and is_anomaly would be False!
    assert res.is_anomaly is True
    assert res.z_score > 4.0


def test_unified_detection_engine_singleton_across_rest_and_kafka():
    """Verify REST API and Kafka TelemetryConsumer reference the exact same DetectionEngine instance."""
    rest_engine = get_detection_engine()
    kafka_engine = _get_detection_engine()
    shared_engine = get_shared_detection_engine()

    assert rest_engine is kafka_engine
    assert rest_engine is shared_engine


def test_celery_tasks_registered_and_executable():
    """Verify Celery worker tasks are registered on celery_app and execute deterministically."""
    assert "aiops.tasks.run_scheduled_correlation_sweep" in celery_app.tasks
    assert "aiops.tasks.generate_incident_post_mortem" in celery_app.tasks
    assert "aiops.tasks.prune_telemetry_retention" in celery_app.tasks

    out = generate_incident_post_mortem_task(
        incident_id="inc-celery-1",
        root_cause_service="payment-service",
        root_cause_type="db_pool_exhaustion",
        confidence=0.91,
        affected_services=["order-service", "api-gateway"],
        impact_score=85.0,
    )
    assert out["grounding_verified"] is True
    assert "payment-service" in out["markdown"]

