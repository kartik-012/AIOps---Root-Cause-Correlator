"""Step 10 Item 4: Detection Engine Robustness & Anti-Poisoning Test Suite.

Verifies:
1. Multi-scale metric handling: error_rate (0.001 scale) vs latency_ms (500.0 scale).
2. Anti-poisoning resilience across 50 sustained anomalous ticks.
3. Immediate post-outage recovery without sticky false alarms.
"""

from datetime import datetime, timezone, timedelta
import pytest
from app.engines.detection_engine import DetectionEngine


def test_detection_engine_multi_scale_metrics():
    """Verify detector correctly identifies anomalies across small-scale and large-scale metrics."""
    engine = DetectionEngine(alpha=0.3, base_threshold=2.5, min_samples=5)
    t0 = datetime(2026, 8, 25, 10, 0, 0, tzinfo=timezone.utc)

    # 1. Small scale: error_rate (nominal ~0.001, spike ~0.08)
    for i in range(10):
        engine.process_metric("order-svc", "error_rate", 0.001 + (0.0001 if i % 2 == 0 else -0.0001), t0 + timedelta(seconds=i * 10))

    spike_res = engine.process_metric("order-svc", "error_rate", 0.08, t0 + timedelta(seconds=110))
    assert spike_res.is_anomaly is True
    assert spike_res.severity in ("high", "critical")

    # 2. Large scale: latency_ms (nominal ~250.0ms, spike ~2800.0ms)
    for i in range(10):
        engine.process_metric("order-svc", "latency_ms", 250.0 + (5.0 if i % 2 == 0 else -5.0), t0 + timedelta(seconds=i * 10))

    spike_latency_res = engine.process_metric("order-svc", "latency_ms", 2800.0, t0 + timedelta(seconds=110))
    assert spike_latency_res.is_anomaly is True
    assert spike_latency_res.severity in ("high", "critical")


def test_sustained_outage_resists_baseline_poisoning_and_recovers():
    """Verify that 50 sustained anomalous ticks do not poison the baseline due to outlier damping."""
    engine = DetectionEngine(alpha=0.3, base_threshold=2.5, min_samples=10)
    t0 = datetime(2026, 8, 25, 8, 0, 0, tzinfo=timezone.utc)

    # Burn in nominal baseline (mean ~100.0)
    for i in range(15):
        engine.process_metric("payment-svc", "latency_ms", 100.0 + (2.0 if i % 2 == 0 else -2.0), t0 + timedelta(seconds=i * 10))

    state_before_outage = engine._get_or_create_state("payment-svc", "latency_ms")
    baseline_mean = state_before_outage.mean
    assert 98.0 <= baseline_mean <= 102.0

    # Inject sustained 50 ticks of major outage (~1500.0ms)
    outage_start = t0 + timedelta(seconds=200)
    for i in range(50):
        res = engine.process_metric("payment-svc", "latency_ms", 1500.0, outage_start + timedelta(seconds=i * 10))
        assert res.is_anomaly is True, f"Tick {i} during outage failed to be detected as anomaly"

    # Outlier damping (alpha_anom = 0.02) and residual clipping should have prevented baseline from reaching 1500.0
    state_after_outage = engine._get_or_create_state("payment-svc", "latency_ms")
    assert state_after_outage.mean < 1000.0, (
        f"Baseline was poisoned to {state_after_outage.mean}, expected damping to keep it well below 1000.0"
    )

    # Immediate recovery back to nominal ~100.0ms
    recovery_time = outage_start + timedelta(seconds=550)
    recovered_res = engine.process_metric("payment-svc", "latency_ms", 100.0, recovery_time)
    assert recovered_res.is_anomaly is False, "Detector fired false alarm immediately after recovery"
