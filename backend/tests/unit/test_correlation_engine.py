"""Unit tests for Correlation Engine — graph-based root cause identification and multi-incident separation."""

from datetime import datetime, timezone, timedelta
import pytest

from app.graph.dependency_graph import DependencyGraph
from app.engines.correlation_engine import CorrelationEngine, AnomalyEvent


@pytest.fixture
def sample_topology():
    """Topology:
    gateway -> auth
    gateway -> order -> payment
    order -> inventory
    """
    g = DependencyGraph()
    g.add_service("gateway", "API Gateway", revenue_weight=10.0)
    g.add_service("auth", "Auth Service", revenue_weight=5.0)
    g.add_service("order", "Order Service", revenue_weight=8.0)
    g.add_service("payment", "Payment Service", revenue_weight=9.0)
    g.add_service("inventory", "Inventory Service", revenue_weight=6.0)

    g.add_dependency("gateway", "auth")
    g.add_dependency("gateway", "order")
    g.add_dependency("order", "payment")
    g.add_dependency("order", "inventory")
    return g


def test_single_root_cause_cascade(sample_topology):
    """Payment fails first -> cascades to Order -> then Gateway."""
    engine = CorrelationEngine(sample_topology)
    t0 = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)

    anomalies = [
        # Payment fails at t0
        AnomalyEvent(service_id="payment", metric_type="connection_pool", z_score=4.5, severity="critical", detected_at=t0),
        # Order cascades at t0 + 10s
        AnomalyEvent(service_id="order", metric_type="latency_ms", z_score=3.2, severity="high", detected_at=t0 + timedelta(seconds=10)),
        # Gateway cascades at t0 + 20s
        AnomalyEvent(service_id="gateway", metric_type="error_rate", z_score=2.8, severity="medium", detected_at=t0 + timedelta(seconds=20)),
    ]

    incidents = engine.correlate(anomalies)

    assert len(incidents) == 1
    inc = incidents[0]
    assert inc.root_cause_service_id == "payment"
    assert inc.root_cause_type == "db_connection_exhaustion"
    assert inc.is_multi_root_cause is False
    assert inc.confidence > 0.70
    assert "order" in inc.affected_service_ids
    assert "gateway" in inc.affected_service_ids


def test_multi_root_cause_separation(sample_topology):
    """Auth fails independently from Payment. Must separate into 2 distinct incidents."""
    engine = CorrelationEngine(sample_topology)
    t0 = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)

    anomalies = [
        # Incident 1: Payment fails -> cascades to order
        AnomalyEvent(service_id="payment", metric_type="cpu_usage", z_score=4.2, severity="critical", detected_at=t0),
        AnomalyEvent(service_id="order", metric_type="latency_ms", z_score=3.0, severity="high", detected_at=t0 + timedelta(seconds=5)),

        # Incident 2: Auth fails independently
        AnomalyEvent(service_id="auth", metric_type="memory_usage", z_score=3.8, severity="high", detected_at=t0 + timedelta(seconds=2)),
    ]

    incidents = engine.correlate(anomalies)

    assert len(incidents) == 2, f"Expected 2 separate incidents, got {len(incidents)}"
    roots = {inc.root_cause_service_id for inc in incidents}
    assert "payment" in roots
    assert "auth" in roots
    for inc in incidents:
        assert inc.is_multi_root_cause is True


def test_lagged_cross_correlation_linear_pearson():
    """Differentiator #4: Verify tau-shifted Pearson r(tau) identifies exact propagation lag tau=2."""
    from app.engines.correlation_engine import compute_lagged_cross_correlation

    # Cause spikes at index 4..6; Effect spikes 2 steps later at index 6..8
    series_cause = [10.0, 10.5, 9.8, 10.2, 85.0, 140.0, 95.0, 12.0, 10.1, 9.9, 10.0, 10.2]
    series_effect = [20.0, 19.5, 20.4, 19.8, 20.1, 20.0, 170.0, 280.0, 190.0, 24.0, 20.2, 19.8]

    res = compute_lagged_cross_correlation(
        series_cause=series_cause,
        series_effect=series_effect,
        max_lag=4,
        cause_service_id="payment",
        effect_service_id="order",
    )

    assert res.optimal_lag_steps == 2
    assert res.max_pearson_r > 0.98
    assert res.is_causally_aligned is True
    assert res.lag_profile[2] > res.lag_profile[0]


def test_lagged_cross_correlation_nonlinear_spearman():
    """Differentiator #4: Verify Spearman rho(tau) captures non-linear monotonic saturation cascades."""
    from app.engines.correlation_engine import compute_lagged_cross_correlation

    base_signal = [1.0, 2.0, 1.5, 3.0, 5.0, 8.0, 12.0, 4.0, 2.5, 1.2]
    # Effect lags by tau=1 and responds exponentially/non-linearly (x^4)
    series_cause = base_signal + [1.0, 1.1]
    series_effect = [1.0] + [x ** 4 for x in base_signal] + [1.0]

    res = compute_lagged_cross_correlation(
        series_cause=series_cause,
        series_effect=series_effect,
        max_lag=3,
        cause_service_id="redis",
        effect_service_id="auth",
    )

    assert res.optimal_lag_steps == 1
    assert res.max_spearman_rho >= 0.95
    assert res.max_spearman_rho > res.max_pearson_r
    assert res.is_causally_aligned is True


def test_correlate_with_metric_streams_boosts_aligned_and_penalizes_uncorrelated(sample_topology):
    """Differentiator #4: Verify CorrelationEngine.correlate adjusts confidence based on metric stream alignment."""
    engine = CorrelationEngine(sample_topology)
    t0 = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)

    anomalies = [
        AnomalyEvent(service_id="payment", metric_type="connection_pool", z_score=4.2, severity="critical", detected_at=t0),
        AnomalyEvent(service_id="order", metric_type="latency_ms", z_score=3.4, severity="high", detected_at=t0 + timedelta(seconds=10)),
    ]

    baseline_inc = engine.correlate(anomalies)[0]

    # Case 1: Causally aligned metric streams (payment leads order by tau=1)
    aligned_streams = {
        "payment": [10.0, 11.0, 10.5, 90.0, 150.0, 110.0, 12.0, 10.0, 9.5, 10.2],
        "order": [20.0, 21.0, 20.5, 21.0, 180.0, 300.0, 220.0, 24.0, 20.0, 19.5],
    }
    aligned_inc = engine.correlate(anomalies, metric_streams=aligned_streams)[0]
    assert len(aligned_inc.lagged_correlations) == 1
    assert aligned_inc.lagged_correlations[0].is_causally_aligned is True
    assert aligned_inc.confidence >= baseline_inc.confidence

    # Case 2: Uncorrelated / reverse spike streams (order spiked at index 1, payment spiked at index 8)
    unaligned_streams = {
        "payment": [10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 10.0, 150.0, 10.0],
        "order": [20.0, 300.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0, 20.0],
    }
    unaligned_inc = engine.correlate(anomalies, metric_streams=unaligned_streams)[0]
    assert len(unaligned_inc.lagged_correlations) == 1
    assert unaligned_inc.lagged_correlations[0].is_causally_aligned is False
    assert unaligned_inc.confidence < aligned_inc.confidence


def test_change_event_correlation_within_and_outside_window(sample_topology):
    """Differentiator #5: Verify Git SHA / Config deploy overlay within <= 15m boosts confidence and attaches suspect_deployment."""
    from app.engines.correlation_engine import ChangeEvent

    engine = CorrelationEngine(sample_topology)
    t0 = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)

    anomalies = [
        AnomalyEvent(service_id="payment", metric_type="error_rate", z_score=3.8, severity="high", detected_at=t0),
        AnomalyEvent(service_id="order", metric_type="latency_ms", z_score=3.1, severity="high", detected_at=t0 + timedelta(seconds=15)),
    ]

    baseline_inc = engine.correlate(anomalies)[0]
    assert baseline_inc.suspect_deployment is None

    # Case 1: Deployment on payment 4 minutes before anomaly onset (within <= 15 min window)
    recent_deploy = ChangeEvent(
        service_id="payment",
        git_sha="a91f4c82b01d",
        config_version="cfg-2026.08.25-v3",
        deployed_by="github-actions",
        deployed_at=t0 - timedelta(minutes=4),
    )
    inc_with_deploy = engine.correlate(anomalies, change_events=[recent_deploy])[0]
    assert inc_with_deploy.suspect_deployment is not None
    assert inc_with_deploy.suspect_deployment.git_sha == "a91f4c82b01d"
    assert inc_with_deploy.suspect_deployment.config_version == "cfg-2026.08.25-v3"
    assert inc_with_deploy.suspect_deployment.minutes_before_onset == 4.0
    assert inc_with_deploy.suspect_deployment.proximity_boost > 0.08
    assert inc_with_deploy.confidence > baseline_inc.confidence

    # Case 2: Deployment 45 minutes before onset (outside 15m window) or 5 minutes AFTER onset (delta < 0)
    stale_deploy = ChangeEvent(
        service_id="payment",
        git_sha="old000111222",
        deployed_at=t0 - timedelta(minutes=45),
    )
    future_deploy = ChangeEvent(
        service_id="payment",
        git_sha="post99988877",
        deployed_at=t0 + timedelta(minutes=5),
    )
    inc_no_match = engine.correlate(anomalies, change_events=[stale_deploy, future_deploy])[0]
    assert inc_no_match.suspect_deployment is None
    assert inc_no_match.confidence == baseline_inc.confidence


def test_cycle_safe_personalized_pagerank_bidirectional_cycle():
    """Differentiator #6: Verify circular dependency (order <-> auth) ranks true causal origin via Personalized PageRank."""
    g = DependencyGraph()
    g.add_service("gateway", "API Gateway", revenue_weight=10.0)
    g.add_service("order", "Order Service", revenue_weight=8.0)
    g.add_service("auth", "Auth Service", revenue_weight=7.0)

    # Bidirectional cycle: order <-> auth, with gateway -> order
    g.add_dependency("gateway", "order")
    g.add_dependency("order", "auth")
    g.add_dependency("auth", "order")

    engine = CorrelationEngine(g)
    t0 = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)

    anomalies = [
        # Gateway fails last (upstream caller)
        AnomalyEvent(service_id="gateway", metric_type="error_rate", z_score=2.7, severity="medium", detected_at=t0 + timedelta(seconds=20)),
        # Order fails second (in cycle)
        AnomalyEvent(service_id="order", metric_type="latency_ms", z_score=3.2, severity="high", detected_at=t0 + timedelta(seconds=10)),
        # Auth fails first with highest severity (true root cause inside cycle)
        AnomalyEvent(service_id="auth", metric_type="connection_pool", z_score=5.2, severity="critical", detected_at=t0),
    ]

    incidents = engine.correlate(anomalies)
    assert len(incidents) == 1
    inc = incidents[0]
    assert inc.cycle_detected is True
    assert inc.root_cause_service_id == "auth"
    assert inc.pagerank_scores["auth"] > inc.pagerank_scores["order"]
    assert inc.pagerank_scores["order"] > inc.pagerank_scores["gateway"]
    assert "order" in inc.affected_service_ids
    assert "gateway" in inc.affected_service_ids


def test_cycle_safe_three_node_ring_with_upstream_caller():
    """Differentiator #6: Verify 3-node ring (svc_a -> svc_b -> svc_c -> svc_a) isolates svc_c as root cause."""
    g = DependencyGraph()
    for sid in ["edge_router", "svc_a", "svc_b", "svc_c"]:
        g.add_service(sid, sid.upper(), revenue_weight=5.0)

    g.add_dependency("edge_router", "svc_a")
    g.add_dependency("svc_a", "svc_b")
    g.add_dependency("svc_b", "svc_c")
    g.add_dependency("svc_c", "svc_a")

    engine = CorrelationEngine(g)
    t0 = datetime(2026, 8, 25, 14, 0, 0, tzinfo=timezone.utc)

    anomalies = [
        AnomalyEvent(service_id="svc_c", metric_type="memory_usage", z_score=5.5, severity="critical", detected_at=t0),
        AnomalyEvent(service_id="svc_b", metric_type="latency_ms", z_score=3.4, severity="high", detected_at=t0 + timedelta(seconds=12)),
        AnomalyEvent(service_id="svc_a", metric_type="latency_ms", z_score=3.0, severity="high", detected_at=t0 + timedelta(seconds=24)),
        AnomalyEvent(service_id="edge_router", metric_type="error_rate", z_score=2.6, severity="medium", detected_at=t0 + timedelta(seconds=36)),
    ]

    incidents = engine.correlate(anomalies)
    assert len(incidents) == 1
    inc = incidents[0]
    assert inc.cycle_detected is True
    assert inc.root_cause_service_id == "svc_c"
    assert inc.pagerank_scores["svc_c"] == max(inc.pagerank_scores.values())



