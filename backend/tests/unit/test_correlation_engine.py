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
