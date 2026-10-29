"""Unit and integration tests for the 4 Principal SRE features (A, B, C, D) and Tier 1 API wiring."""

from datetime import datetime, timezone, timedelta
import math
import pytest

from app.engines.trace_attribution_engine import TraceAttributionEngine, TraceSpan
from app.engines.detection_engine import DetectionEngine
from app.engines.remediation_engine import ThompsonSamplingRunbookBandit
from app.engines.chaos_gameday_engine import ChaosGameDayEngine


def test_feature_a_opentelemetry_trace_critical_path_span_attribution():
    """Verify Feature A: OpenTelemetry Trace Critical-Path Engine subtracts overlapping child spans
    and isolates the exact SQL/gRPC leaf span responsible for >85% of tail latency.
    """
    engine = TraceAttributionEngine()
    spans = engine.synthesize_cascade_trace(
        trace_id="trace-9901",
        root_cause_service="payment-service",
        fault_type="db_pool_exhaustion",
    )
    report = engine.analyze_trace(spans)

    assert report.trace_id == "trace-9901"
    assert report.bottleneck_service == "payment-service"
    assert report.bottleneck_span_id == "span-root-05"
    assert "PostgreSQL SELECT" in report.bottleneck_operation
    assert report.bottleneck_contribution_pct > 85.0
    assert report.critical_path_services == ["api-gateway", "order-service", "payment-service"]


def test_feature_a_parallel_overlapping_child_spans_interval_merging():
    """Verify parallel overlapping child spans are interval-merged so parent exclusive duration is never negative."""
    engine = TraceAttributionEngine()
    spans = [
        TraceSpan("root", "t1", "api-gateway", "GET /home", 0.0, 100.0, None),
        # Two parallel child calls that both run from t=10ms to t=90ms (80ms overlap)
        TraceSpan("c1", "t1", "auth-service", "CheckAuth", 10.0, 80.0, "root"),
        TraceSpan("c2", "t1", "product-catalog", "FetchCatalog", 10.0, 80.0, "root"),
    ]
    report = engine.analyze_trace(spans)
    by_id = {n.span_id: n for n in report.span_attributions}
    # Parent spent 80ms waiting on the parallel fan-out, so its exclusive self-time is 100 - 80 = 20ms
    assert abs(by_id["root"].exclusive_duration_ms - 20.0) < 1e-6


def test_feature_b_diurnal_seasonal_harmonic_9am_traffic_ramp_vs_3am_spike():
    """Verify Feature B: 24-Hour Fourier Harmonic Diurnal Baseline recognizes expected 9:00 AM traffic surge
    (65% CPU) as normal while flagging the exact same 65% CPU at 3:00 AM as a critical anomaly.
    """
    engine = DetectionEngine(alpha=0.3, base_threshold=3.0, min_samples=3, redis_client=None)
    base_day = datetime(2026, 10, 10, 0, 0, 0, tzinfo=timezone.utc)

    # Generate 3 days of 24-hour diurnal CPU telemetry:
    # Low ~15% at 03:00 UTC, peaking ~65% at 09:00 UTC
    observations = []
    for hour_offset in range(72):
        ts = base_day + timedelta(hours=hour_offset)
        hour_of_day = ts.hour
        # Smooth diurnal curve peaking at 9:00 AM (65%) and troughing at 21:00/03:00 (~15%)
        phase = ((hour_of_day - 9.0) / 24.0) * 2.0 * math.pi
        val = 40.0 + 25.0 * math.cos(phase)
        observations.append((ts, val))

    engine.fit_diurnal_profile("api-gateway", "cpu_usage", observations)

    # 1. Evaluate 65.0% CPU at 09:00 AM (expected morning peak) -> should NOT be an anomaly
    ts_9am = datetime(2026, 10, 13, 9, 0, 0, tzinfo=timezone.utc)
    res_9am = engine.process_seasonal_metric("api-gateway", "cpu_usage", 65.0, ts_9am)
    assert res_9am.is_anomaly is False
    assert abs(res_9am.z_score) < 2.0

    # 2. Evaluate the exact same 65.0% CPU at 03:00 AM (off-peak night hours) -> MUST be a critical anomaly!
    ts_3am = datetime(2026, 10, 13, 3, 0, 0, tzinfo=timezone.utc)
    res_3am = engine.process_seasonal_metric("api-gateway", "cpu_usage", 65.0, ts_3am)
    assert res_3am.is_anomaly is True
    assert res_3am.severity == "critical"
    assert res_3am.z_score > 5.0


def test_feature_c_thompson_sampling_multi_armed_bandit_online_runbook_ranking():
    """Verify Feature C: Beta-Bernoulli Thompson Sampling bandit learns online from remediation outcomes
    and promotes high-success, low-MTTR runbooks above failing ones.
    """
    bandit = ThompsonSamplingRunbookBandit(seed=101)
    candidates = [
        {"action_id": "restart_pod", "title": "Restart Pod Immediately"},
        {"action_id": "scale_pgbouncer_pool", "title": "Scale PgBouncer Pool & Drain Idle"},
    ]

    # Simulate 6 production incidents where restart_pod fails to fix DB pool exhaustion,
    # while scale_pgbouncer_pool succeeds rapidly in 8 seconds.
    for _ in range(6):
        bandit.record_outcome("db_pool_exhaustion", "restart_pod", resolved=False, mttr_seconds=120.0)
        bandit.record_outcome("db_pool_exhaustion", "scale_pgbouncer_pool", resolved=True, mttr_seconds=8.0)

    ranked = bandit.rank_runbooks("db_pool_exhaustion", candidates, explore=False)
    assert ranked[0]["action_id"] == "scale_pgbouncer_pool"
    assert ranked[0]["posterior_success_prob"] > 0.85
    assert ranked[1]["action_id"] == "restart_pod"
    assert ranked[1]["posterior_success_prob"] < 0.30


@pytest.mark.asyncio
async def test_feature_d_automated_chaos_gameday_scenario_runner():
    """Verify Feature D: Automated 4-stage Chaos GameDay runner executes Fault Injection -> Detection ->
    MicroRCA++ & Trace Isolation -> Canary Remediation & Bandit Learning end-to-end.
    """
    gameday = ChaosGameDayEngine()
    report = await gameday.run_gameday_drill(
        scenario_name="db_pool_exhaustion",
        root_service="payment-service",
    )

    assert report.root_cause_accurate is True
    assert report.isolated_root_service == "payment-service"
    assert report.confidence > 0.70
    assert report.mttd_ms > 0.0
    assert report.mtti_ms > 0.0
    assert report.mttr_ms > 0.0
    assert len(report.timeline_stages) == 4
    assert report.trace_critical_path["bottleneck_service"] == "payment-service"
    assert report.canary_remediation["canary_status"] == "CANARY_SUCCESS"
    assert report.bandit_posterior["trials"] >= 1


def test_feature_b_diurnal_baseline_bounds():
    """Verify diurnal baseline prediction maintains valid numerical bounds across 24 hours."""
    from app.engines.detection_engine import DiurnalSeasonalBaseline
    diurnal = DiurnalSeasonalBaseline()
    for hour in range(24):
        dt = datetime(2026, 10, 29, hour, 0, tzinfo=timezone.utc)
        expected, z = diurnal.predict_and_score(dt, 25.0)
        assert isinstance(expected, (int, float))
        assert isinstance(z, (int, float))
        assert not math.isnan(expected)
        assert not math.isnan(z)
