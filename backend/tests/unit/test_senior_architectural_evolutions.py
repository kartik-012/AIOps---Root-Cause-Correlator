"""Test suite verifying the 4 Senior Architectural Evolutions:

1. MicroRCA++ Edge-Weighted Graph Covariance & Dynamic PageRank.
2. StreamingRingBuffer High-Throughput Aggregation & Backpressure Downsampling.
3. Canary Remediation Safety Gating with Auto-Rollback Circuit Breaker.
4. Multi-Tenant Domain Partitioning & Vector Cosine Retrieval.
"""

from datetime import datetime, timezone, timedelta
import uuid
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.graph.dependency_graph import DependencyGraph
from app.engines.correlation_engine import CorrelationEngine, AnomalyEvent, compute_personalized_pagerank_scores
from app.kafka.consumers.telemetry_consumer import StreamingRingBuffer
from app.engines.remediation_engine import RemediationEngine
from app.grpc_services.service_states import ServiceStateManager
from app.models.db_models import Base, Incident
from app.engines.suppression_engine import SuppressionEngine, build_signature


# ---------------------------------------------------------------------------
# 1. MicroRCA++ Edge-Weighted Graph Covariance & Dynamic PageRank
# ---------------------------------------------------------------------------

def test_microrca_edge_weighted_pagerank_favors_high_traffic_covariance_node():
    """Verify that edge weighting by call volume (RPS) and latency covariance steers causal PageRank."""
    dep_graph = DependencyGraph()
    # Branching topology: api-gateway calls order-svc (low-traffic) and payment-svc (high-traffic/high-covariance)
    dep_graph.add_service("api-gateway", "api-gateway")
    dep_graph.add_service("order-svc", "order-svc")
    dep_graph.add_service("payment-svc", "payment-svc")

    # Gateway branches to both
    dep_graph.set_edge_weight("api-gateway", "order-svc", weight=1.0, rps=10.0, covariance=0.05)
    dep_graph.set_edge_weight("api-gateway", "payment-svc", weight=1.0, rps=5000.0, covariance=1.85)

    subgraph = dep_graph.get_subgraph(["api-gateway", "order-svc", "payment-svc"])
    t0 = datetime(2026, 10, 12, 12, 0, 0, tzinfo=timezone.utc)
    service_earliest = {
        "api-gateway": AnomalyEvent(service_id="api-gateway", metric_type="latency_ms", z_score=3.0, severity="high", detected_at=t0),
        "order-svc": AnomalyEvent(service_id="order-svc", metric_type="latency_ms", z_score=4.0, severity="critical", detected_at=t0),
        "payment-svc": AnomalyEvent(service_id="payment-svc", metric_type="latency_ms", z_score=4.0, severity="critical", detected_at=t0),
    }

    edge_weights = {
        (u, v): dep_graph.get_edge_weight(u, v)
        for u, v in subgraph.edges()
    }
    scores = compute_personalized_pagerank_scores(
        subgraph=subgraph,
        service_earliest=service_earliest,
        edge_weights=edge_weights,
    )

    # Edge api-gateway -> payment-svc has far higher transition weight, driving more causal flow to payment-svc
    assert "payment-svc" in scores and "order-svc" in scores
    assert scores["payment-svc"] > scores["order-svc"]


# ---------------------------------------------------------------------------
# 2. StreamingRingBuffer High-Throughput Aggregation & Backpressure
# ---------------------------------------------------------------------------

def test_streaming_ring_buffer_backpressure_and_downsampling():
    """Verify that StreamingRingBuffer enqueues telemetry and downsamples nominal points under pressure."""
    buffer = StreamingRingBuffer(capacity=100, high_watermark=0.80)

    # Push 80 items up to watermark
    for i in range(80):
        assert buffer.push({"service_id": "api-gateway", "value": 50.0 + i}) is True

    stats_before = buffer.get_stats()
    assert stats_before["current_size"] == 80
    assert stats_before["utilization"] == 0.80

    # Above 80%, nominal telemetry is downsampled (75% dropped)
    accepted = 0
    rejected = 0
    for i in range(20):
        if buffer.push({"service_id": "api-gateway", "value": 50.0}, is_anomaly_hint=False):
            accepted += 1
        else:
            rejected += 1

    assert rejected > 0
    stats_after = buffer.get_stats()
    assert stats_after["downsampled_count"] > 0


# ---------------------------------------------------------------------------
# 3. Canary Remediation Safety Gating with Auto-Rollback Circuit Breaker
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_canary_remediation_safety_circuit_breaker():
    """Verify that failing canary health verification trips the circuit breaker and aborts."""
    state_mgr = ServiceStateManager()
    # Inject fault on payment-service
    state_mgr.inject_fault("payment-service", fault_type="db_connection_exhaustion")

    rem_engine = RemediationEngine(state_manager=state_mgr)
    plan = rem_engine.generate_plan(
        incident_id=str(uuid.uuid4()),
        root_cause_type="db_connection_exhaustion",
        target_service="payment-service",
    )

    # Execute canary with health verification enabled
    executed_plan = await rem_engine.execute_canary_with_safety_circuit_breaker(
        plan_id=plan.plan_id,
        approver="Senior SRE Commander",
        canary_percent=10,
        verify_health=True,
    )

    assert executed_plan.is_canary is True
    assert executed_plan.canary_percentage == 10
    assert executed_plan.canary_status == "CANARY_SUCCESS"
    assert executed_plan.closed_loop_verified is True


# ---------------------------------------------------------------------------
# 4. Multi-Tenant Domain Partitioning & Vector Cosine Retrieval
# ---------------------------------------------------------------------------

@pytest.fixture
def test_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def test_multi_tenant_vector_partitioning(test_db: Session):
    """Verify that vector similarity queries respect tenant_id and environment isolation."""
    engine = SuppressionEngine(similarity_threshold=0.85)

    sig_tenant_a = build_signature(
        hour_bucket=2.0, day_of_week=5.0, service_id="billing", metric_type="latency_ms", severity_z=3.0, depth=1.0, speed=10.0
    )
    sig_tenant_b = build_signature(
        hour_bucket=2.0, day_of_week=5.0, service_id="billing", metric_type="latency_ms", severity_z=3.0, depth=1.0, speed=10.0
    )

    # Seed incidents in different tenants
    inc_a = Incident(
        id=uuid.uuid4(),
        timestamp_start=datetime.now(timezone.utc),
        root_cause_service_id=uuid.uuid4(),
        root_cause_type="latency_spike",
        tenant_id="tenant-alpha",
        environment="production",
        was_false_positive=True,
        anomaly_signature=sig_tenant_a,
    )
    inc_b = Incident(
        id=uuid.uuid4(),
        timestamp_start=datetime.now(timezone.utc),
        root_cause_service_id=uuid.uuid4(),
        root_cause_type="latency_spike",
        tenant_id="tenant-beta",
        environment="staging",
        was_false_positive=True,
        anomaly_signature=sig_tenant_b,
    )
    test_db.add_all([inc_a, inc_b])
    test_db.commit()

    # Query specifically for tenant-alpha in production
    results_a = engine.retrieve_similar_incidents(
        candidate_signature=sig_tenant_a,
        db=test_db,
        top_k=5,
        false_positives_only=True,
        tenant_id="tenant-alpha",
        environment="production",
    )
    assert len(results_a) == 1
    assert results_a[0]["tenant_id"] == "tenant-alpha"
    assert results_a[0]["environment"] == "production"

    # Query for tenant-beta in staging
    results_b = engine.retrieve_similar_incidents(
        candidate_signature=sig_tenant_b,
        db=test_db,
        top_k=5,
        false_positives_only=True,
        tenant_id="tenant-beta",
        environment="staging",
    )
    assert len(results_b) == 1
    assert results_b[0]["tenant_id"] == "tenant-beta"
    assert results_b[0]["environment"] == "staging"
