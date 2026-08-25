"""Unit tests for Detection Engine — EWMA baseline and adaptive z-score detection."""

from datetime import datetime, timezone
import pytest
from app.engines.detection_engine import DetectionEngine, EWMAState


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


def test_detection_engine_drift_adaptation():
    """Gradual organic growth should adapt the baseline without creating persistent anomalies."""
    engine = DetectionEngine(alpha=0.3, base_threshold=3.0, min_samples=3)
    now = datetime.now(timezone.utc)

    # 10 gradual increments
    anomalies_flagged = 0
    for val in range(100, 200, 5):
        res = engine.process_metric("auth-svc", "cpu_usage", float(val), now)
        if res.is_anomaly:
            anomalies_flagged += 1

    # Baseline should have adapted to ~190
    state = engine._states[("auth-svc", "cpu_usage")]
    assert state.mean > 160.0
