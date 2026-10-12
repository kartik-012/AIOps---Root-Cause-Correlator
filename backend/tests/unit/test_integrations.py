"""Unit tests for Integrations: Slack Alerts, LLM Post-Mortem, and OpenTelemetry ingestion."""

import pytest
from app.services.slack_notifier import SlackNotifier
from app.services.llm_report_generator import LLMReportGenerator


@pytest.mark.asyncio
async def test_slack_notifier_payload_generation():
    notifier = SlackNotifier()
    res = await notifier.send_incident_alert(
        incident_id="test-inc-123",
        root_cause_service="payment-service",
        root_cause_type="db_connection_exhaustion",
        confidence=0.94,
        affected_services=["order-service", "api-gateway"],
        impact_score=87.0,
    )
    assert res["status"] == "simulated"
    payload = res["payload"]
    assert "payment-service" in payload["text"]
    assert len(payload["blocks"]) >= 4


def test_llm_post_mortem_generator():
    generator = LLMReportGenerator()
    report = generator.generate_post_mortem(
        incident_id="test-inc-456",
        root_cause_service="payment-service",
        root_cause_type="db_connection_exhaustion",
        confidence=0.95,
        affected_services=["order-service", "api-gateway"],
        impact_score=88.0,
    )
    assert "INCIDENT POST-MORTEM REPORT" in report["markdown"]
    assert "payment-service" in report["markdown"]
    assert report["mttd"] == "0.42s"
    assert report["grounding_verified"] is True
    assert "$41,580" in report["financial_exposure"]


def test_otel_dynamic_trace_to_topology_discovery_upserts_edges_with_last_seen_at():
    """Verify Differentiator #2: ingest_opentelemetry automatically links parent-child spans
    and peer_service attributes to upsert directed ServiceDependency edges with last_seen_at.
    """
    from datetime import datetime, timezone, timedelta
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker
    from app.models.db_models import Base, Service, ServiceDependency
    from app.api.v1.integrations import ingest_opentelemetry, OtelPayload, OtelSpan

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    t1 = datetime(2026, 10, 12, 16, 0, 0, tzinfo=timezone.utc)
    t2 = t1 + timedelta(minutes=5)

    with SessionLocal() as db:
        payload_1 = OtelPayload(
            spans=[
                OtelSpan(
                    name="POST /checkout",
                    service_name="api-gateway",
                    duration_ms=45.0,
                    trace_id="trace-abc-1",
                    span_id="span-gw-1",
                    timestamp=t1,
                ),
                OtelSpan(
                    name="CreateOrder",
                    service_name="order-service",
                    duration_ms=30.0,
                    trace_id="trace-abc-1",
                    span_id="span-ord-1",
                    parent_span_id="span-gw-1",
                    timestamp=t1,
                ),
                OtelSpan(
                    name="ChargeCard",
                    service_name="payment-service",
                    duration_ms=18.0,
                    trace_id="trace-abc-1",
                    span_id="span-pay-1",
                    parent_span_id="span-ord-1",
                    peer_service="fraud-detection-service",
                    timestamp=t1,
                ),
            ]
        )
        res1 = ingest_opentelemetry(payload_1, db)
        assert res1["status"] == "processed"
        edges_1 = {
            (d["from_service"], d["to_service"]): d
            for d in res1["discovered_dependencies"]
        }
        assert ("api-gateway", "order-service") in edges_1
        assert ("order-service", "payment-service") in edges_1
        assert ("payment-service", "fraud-detection-service") in edges_1
        assert all(d["is_new_edge"] is True for d in edges_1.values())

        # Verify 4 services and 3 directed edges persisted in DB
        all_svcs = db.scalars(select(Service)).all()
        all_deps = db.scalars(select(ServiceDependency)).all()
        assert len(all_svcs) == 4
        assert len(all_deps) == 3
        assert all(dep.last_seen_at is not None for dep in all_deps)

        # Second trace touching api-gateway -> order-service at t2 must update last_seen_at (is_new_edge=False)
        payload_2 = OtelPayload(
            spans=[
                OtelSpan(
                    name="GET /orders",
                    service_name="api-gateway",
                    duration_ms=20.0,
                    trace_id="trace-abc-2",
                    span_id="span-gw-2",
                    timestamp=t2,
                ),
                OtelSpan(
                    name="FetchOrders",
                    service_name="order-service",
                    duration_ms=12.0,
                    trace_id="trace-abc-2",
                    span_id="span-ord-2",
                    parent_span_id="span-gw-2",
                    timestamp=t2,
                ),
            ]
        )
        res2 = ingest_opentelemetry(payload_2, db)
        assert len(res2["discovered_dependencies"]) == 1
        updated_edge = res2["discovered_dependencies"][0]
        assert updated_edge["from_service"] == "api-gateway"
        assert updated_edge["to_service"] == "order-service"
        assert updated_edge["is_new_edge"] is False
        assert updated_edge["last_seen_at"] == t2.isoformat()

        # Total edge count remains 3 (idempotent upsert)
        assert len(db.scalars(select(ServiceDependency)).all()) == 3


def test_deployment_event_ingestion_and_listing():
    """Differentiator #5: Verify POST /deployments and GET /deployments persist and return Git SHA & config rollout events."""
    from datetime import datetime, timezone
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.models.db_models import Base
    from app.api.v1.integrations import (
        ingest_deployment_event,
        list_deployment_events,
        DeploymentEventRequest,
    )

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    deploy_ts = datetime(2026, 10, 12, 17, 30, 0, tzinfo=timezone.utc)
    with SessionLocal() as db:
        req = DeploymentEventRequest(
            service_name="payment-service",
            git_sha="7f3b91c4e201",
            config_version="v2.14.0-pool-limit",
            deployed_by="argocd-sync",
            environment="production",
            deployed_at=deploy_ts,
        )
        res = ingest_deployment_event(req, db)
        assert res["status"] == "recorded"
        assert res["service_name"] == "payment-service"
        assert res["git_sha"] == "7f3b91c4e201"
        assert res["config_version"] == "v2.14.0-pool-limit"

        listed = list_deployment_events(db, limit=10)
        assert len(listed["deployments"]) == 1
        assert listed["deployments"][0]["git_sha"] == "7f3b91c4e201"
        assert listed["deployments"][0]["service_name"] == "payment-service"


def test_llm_citation_verification_and_deterministic_fallback(monkeypatch):
    """Differentiator #7: Verify validate_grounding checks [EVID-k] & anomaly_id citations and falls back on hallucinated citations."""
    from datetime import datetime, timezone
    from app.services.llm_report_generator import LLMReportGenerator, AnomalyEvidenceItem

    # 1. Valid grounded Markdown with verified [EVID-1] and anomaly_id=anom-101
    valid_md = (
        "Root cause isolated to `payment-service` due to connection pool exhaustion "
        "cited in [EVID-1] (anomaly_id=anom-101), cascading to `order-service` [EVID-2]."
    )
    res_ok = LLMReportGenerator.validate_grounding(
        markdown_text=valid_md,
        root_cause_service="payment-service",
        allowed_services=["payment-service", "order-service"],
        valid_citation_ids=["EVID-1", "EVID-2"],
        valid_anomaly_ids=["anom-101"],
    )
    assert res_ok.is_valid is True
    assert res_ok.citation_coverage == 1.0
    assert res_ok.unverified_citations == []

    # 2. Hallucinated citation ID [EVID-99] and fake anomaly_id=anom-999 must be rejected
    bad_citation_md = (
        "Root cause isolated to `payment-service` [EVID-1] and [EVID-99] (anomaly_id=anom-999)."
    )
    res_bad = LLMReportGenerator.validate_grounding(
        markdown_text=bad_citation_md,
        root_cause_service="payment-service",
        allowed_services=["payment-service", "order-service"],
        valid_citation_ids=["EVID-1", "EVID-2"],
        valid_anomaly_ids=["anom-101"],
    )
    assert res_bad.is_valid is False
    assert "EVID-99" in res_bad.unverified_citations
    assert "anomaly_id=anom-999" in res_bad.unverified_citations

    # 3. End-to-end deterministic fallback when LLM returns hallucinated citation [EVID-42]
    gen = LLMReportGenerator(api_key="test-fake-key", provider="openai", model="gpt-4o-mini")
    monkeypatch.setattr(
        gen,
        "_call_llm_provider",
        lambda sys_p, usr_p: "Outage in `payment-service` verified by [EVID-42].",
    )
    t0 = datetime(2026, 10, 12, 17, 0, 0, tzinfo=timezone.utc)
    report = gen.generate_post_mortem(
        incident_id="inc-777",
        root_cause_service="payment-service",
        root_cause_type="db_connection_exhaustion",
        confidence=0.95,
        affected_services=["order-service"],
        impact_score=85.0,
        anomalies=[
            AnomalyEvidenceItem(
                anomaly_id="anom-101",
                service_name="payment-service",
                metric_type="connection_pool",
                z_score=5.1,
                severity="critical",
                detected_at=t0,
            )
        ],
    )
    assert report["llm_fallback_triggered"] is True
    assert report["generation_mode"] == "deterministic_evidence_synthesizer"
    assert "EVID-42" in report["unverified_citations"]
    assert "anomaly_id=anom-101" in report["markdown"]


@pytest.mark.asyncio
async def test_slack_notifier_idempotent_deduplication_redis_and_memory():
    """Differentiator #8: Verify atomic Redis SET NX EX 300 and monotonic memory fallback suppress duplicate alerts."""
    # 1. Test memory TTL deduplication
    notifier = SlackNotifier(dedup_ttl_seconds=300)
    res1 = await notifier.send_incident_alert(
        incident_id="inc-dedup-001",
        root_cause_service="payment-service",
        root_cause_type="db_connection_exhaustion",
        confidence=0.94,
        affected_services=["order-service"],
        impact_score=87.0,
    )
    assert res1["status"] == "simulated"
    assert res1["idempotency_key"] == "alert:dedup:inc-dedup-001"
    assert res1["dedup_backend"] == "memory_ttl"

    res2 = await notifier.send_incident_alert(
        incident_id="inc-dedup-001",
        root_cause_service="payment-service",
        root_cause_type="db_connection_exhaustion",
        confidence=0.94,
        affected_services=["order-service"],
        impact_score=87.0,
    )
    assert res2["status"] == "deduplicated"
    assert res2["cooldown_ttl_seconds"] == 300

    # 2. Test Redis SET alert:dedup:{incident_id} 1 NX EX 300
    class FakeRedis:
        def __init__(self):
            self.store = {}

        async def set(self, key: str, value: str, nx: bool = False, ex: int = 300):
            if nx and key in self.store:
                return None
            self.store[key] = (value, ex)
            return True

    fake_redis = FakeRedis()
    redis_notifier = SlackNotifier(dedup_ttl_seconds=300, redis_client=fake_redis)
    r_first = await redis_notifier.send_incident_alert(
        incident_id="inc-redis-999",
        root_cause_service="auth-service",
        root_cause_type="cpu_spike",
        confidence=0.91,
        affected_services=["api-gateway"],
        impact_score=75.0,
    )
    assert r_first["status"] == "simulated"
    assert r_first["dedup_backend"] == "redis_nx"
    assert fake_redis.store["alert:dedup:inc-redis-999"] == ("1", 300)

    r_dup = await redis_notifier.send_incident_alert(
        incident_id="inc-redis-999",
        root_cause_service="auth-service",
        root_cause_type="cpu_spike",
        confidence=0.91,
        affected_services=["api-gateway"],
        impact_score=75.0,
    )
    assert r_dup["status"] == "deduplicated"
    assert r_dup["dedup_backend"] == "redis_nx"


@pytest.mark.asyncio
async def test_closed_loop_grpc_remediation_restores_service_state_and_persists_db():
    """Differentiator #9: Verify RemediationEngine.approve_and_execute restores degraded ServiceStateManager
    metrics to HEALTHY, verifies closed_loop_verified=True, and persists RunbookSuggestion in DB.
    """
    import uuid
    from datetime import datetime, timezone
    from sqlalchemy import create_engine, select
    from sqlalchemy.orm import sessionmaker
    from app.models.db_models import Base, Service, Incident, RunbookSuggestion
    from app.grpc_services.service_states import ServiceStateManager, HealthStatus
    from app.engines.remediation_engine import RemediationEngine

    state_mgr = ServiceStateManager()
    # 1. Inject db_connection_exhaustion fault on payment-service
    assert state_mgr.inject_fault("payment-service", "db_connection_exhaustion") is True
    degraded = state_mgr.get_state("payment-service", apply_drift=False)
    assert degraded.status == HealthStatus.CRITICAL
    assert degraded.error_rate > 0.1
    assert "High Database Connections" in degraded.active_alerts

    # 2. Set up in-memory DB with Incident
    db_engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(db_engine)
    SessionLocal = sessionmaker(bind=db_engine)

    with SessionLocal() as db:
        svc = Service(name="payment-service", revenue_weight=9.0)
        db.add(svc)
        db.flush()

        inc = Incident(
            timestamp_start=datetime.now(timezone.utc),
            root_cause_service_id=svc.id,
            root_cause_type="db_connection_exhaustion",
            confidence_at_detection=0.95,
        )
        db.add(inc)
        db.commit()

        rem_engine = RemediationEngine(state_manager=state_mgr)
        plan = rem_engine.generate_plan(
            incident_id=str(inc.id),
            root_cause_type="db_connection_exhaustion",
            target_service="Payment Service",
        )
        assert plan.status == "PENDING_APPROVAL"

        executed_plan = await rem_engine.approve_and_execute(
            plan_id=plan.plan_id,
            approver="SRE Commander",
            db=db,
        )
        assert executed_plan.status == "EXECUTED"
        assert executed_plan.closed_loop_verified is True
        assert executed_plan.pre_remediation_health["status"] == HealthStatus.CRITICAL
        assert executed_plan.post_remediation_health["status"] == HealthStatus.HEALTHY
        assert executed_plan.post_remediation_health["error_rate"] == 0.0
        assert executed_plan.post_remediation_health["active_alerts"] == []

        # Verify DB persistence
        refreshed_inc = db.scalar(select(Incident).where(Incident.id == inc.id))
        assert refreshed_inc.resolution_action == plan.action_title
        assert refreshed_inc.timestamp_end is not None

        sugg = db.scalar(select(RunbookSuggestion).where(RunbookSuggestion.incident_id == inc.id))
        assert sugg is not None
        assert sugg.was_approved is True







