"""Unit tests for Prediction, Counterfactual, and Impact Engines."""

from datetime import datetime, timezone, timedelta
import pytest

from app.graph.dependency_graph import DependencyGraph
from app.engines.correlation_engine import AnomalyEvent
from app.engines.prediction_engine import PredictionEngine
from app.engines.counterfactual_engine import CounterfactualEngine
from app.engines.impact_engine import ImpactEngine


@pytest.fixture
def ecommerce_graph():
    """gateway -> order -> payment"""
    g = DependencyGraph()
    g.add_service("gateway", "API Gateway", revenue_weight=10.0)
    g.add_service("order", "Order Service", revenue_weight=8.0)
    g.add_service("payment", "Payment Service", revenue_weight=9.0)
    g.add_service("notify", "Notification", revenue_weight=2.0)

    g.add_dependency("gateway", "order")
    g.add_dependency("order", "payment")
    g.add_dependency("order", "notify")
    return g


def test_prediction_engine_forward_blast_radius(ecommerce_graph):
    engine = PredictionEngine(ecommerce_graph, default_hop_time_seconds=20)
    
    # Payment fails, order and gateway are not yet affected
    result = engine.predict_blast_radius(
        incident_id="inc-1",
        root_cause_service_id="payment",
        already_affected_service_ids=[],
    )

    assert not result.contained
    predicted_services = [p.service_id for p in result.predictions]
    assert "order" in predicted_services
    assert "gateway" in predicted_services

    # Order is 1 hop away -> ETA 20s; Gateway is 2 hops away -> ETA 40s
    order_pred = next(p for p in result.predictions if p.service_id == "order")
    gateway_pred = next(p for p in result.predictions if p.service_id == "gateway")
    assert order_pred.eta_seconds == 20
    assert gateway_pred.eta_seconds == 40
    assert order_pred.confidence > gateway_pred.confidence


def test_counterfactual_engine_simulation(ecommerce_graph):
    engine = CounterfactualEngine(ecommerce_graph)
    t0 = datetime(2026, 8, 25, 12, 0, 0, tzinfo=timezone.utc)

    anomalies = [
        AnomalyEvent(service_id="payment", metric_type="latency_ms", z_score=4.5, severity="critical", detected_at=t0),
        AnomalyEvent(service_id="order", metric_type="latency_ms", z_score=3.2, severity="high", detected_at=t0 + timedelta(seconds=10)),
        AnomalyEvent(service_id="gateway", metric_type="error_rate", z_score=2.8, severity="medium", detected_at=t0 + timedelta(seconds=20)),
    ]

    # Counterfactual: cap payment latency to normal range (z_score <= 1.0)
    sim = engine.simulate(
        original_anomalies=anomalies,
        modified_service_id="payment",
        modified_metric="latency_ms",
        capped_value=1.0,
        normal_threshold=2.0,
    )

    assert sim.would_cascade is False
    assert len(sim.simulated_affected_services) == 0
    assert "order" in sim.mitigated_nodes
    assert "gateway" in sim.mitigated_nodes


def test_impact_engine_scoring(ecommerce_graph):
    engine = ImpactEngine(ecommerce_graph)

    # Payment has callers: order (1) and gateway (2) -> downstream count 2
    # Severity critical (4.0) * revenue_weight (9.0) * (1 + 2) = 108.0
    impact = engine.calculate_impact("payment", severity="critical")
    assert impact.impact_score > 50.0
    assert impact.downstream_dependent_count == 2
    assert impact.severity_label == "critical"
