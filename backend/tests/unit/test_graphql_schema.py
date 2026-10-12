"""Unit tests for the Strawberry GraphQL control plane (session lifecycle, JOIN hydration, and live subscriptions)."""

import asyncio
from datetime import datetime, timezone
import json
import uuid

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.models.db_models import Base, Service, Incident, IncidentAffectedService, Anomaly
from app.graphql.schema import schema, _hydrate_incident_in_session
from app.api.v1.ws import broadcast_event


def _make_sqlite_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)


def test_hydrate_incident_in_session_returns_real_db_rows_without_detached_error():
    """Verify _hydrate_incident_in_session executes inside an active session and returns real DB entities."""
    SessionLocal = _make_sqlite_session()

    with SessionLocal() as db:
        root_svc = Service(id=uuid.uuid4(), name="inventory-service", revenue_weight=8.0)
        victim_svc = Service(id=uuid.uuid4(), name="order-service", revenue_weight=9.0)
        db.add_all([root_svc, victim_svc])
        db.flush()

        inc = Incident(
            id=uuid.uuid4(),
            root_cause_service_id=root_svc.id,
            root_cause_type="cpu_spike",
            confidence_at_detection=0.91,
            timestamp_start=datetime(2026, 10, 12, 10, 0, 0, tzinfo=timezone.utc),
        )
        db.add(inc)
        db.flush()

        ias = IncidentAffectedService(
            incident_id=inc.id,
            service_id=victim_svc.id,
            propagation_order=1,
            affected_at=datetime(2026, 10, 12, 10, 0, 12, tzinfo=timezone.utc),
        )
        anom = Anomaly(
            id=uuid.uuid4(),
            service_id=root_svc.id,
            incident_id=inc.id,
            metric_type="cpu_usage",
            z_score=4.6,
            severity="critical",
            detected_at=datetime(2026, 10, 12, 10, 0, 5, tzinfo=timezone.utc),
        )
        db.add_all([ias, anom])
        db.commit()

        hydrated = _hydrate_incident_in_session(db, inc)

        assert hydrated.id == str(inc.id)
        assert hydrated.root_cause is not None
        assert hydrated.root_cause.service == "inventory-service"
        assert hydrated.root_cause.component == "cpu_spike"
        assert hydrated.root_cause.verification_status == "VERIFIED"
        assert len(hydrated.affected_services) == 1
        assert hydrated.affected_services[0].name == "order-service"
        assert len(hydrated.timeline) == 1
        assert "cpu_usage" in hydrated.timeline[0].event


@pytest.mark.asyncio
async def test_graphql_all_services_health_runs_concurrently():
    """Verify allServicesHealth query resolves all 8 microservice diagnostics concurrently."""
    query = """
    query {
        allServicesHealth {
            serviceId
            status
            p95LatencyMs
        }
    }
    """
    res = await schema.execute(query)
    assert res.errors is None
    items = res.data["allServicesHealth"]
    assert len(items) == 8
    service_ids = {item["serviceId"] for item in items}
    assert "api-gateway" in service_ids
    assert "payment-service" in service_ids


@pytest.mark.asyncio
async def test_graphql_subscription_incident_stream_receives_live_broadcasts():
    """Verify incidentStream subscription receives live events published to broadcast_event()."""
    sub_query = """
    subscription {
        incidentStream(heartbeatSeconds: 0.2, maxEvents: 2)
    }
    """
    sub_gen = await schema.subscribe(sub_query)

    # Emit a real incident event after 50ms
    async def _publish_soon():
        await asyncio.sleep(0.05)
        await broadcast_event({
            "type": "incident_correlated",
            "incident_id": "inc-live-999",
            "root_cause_service": "auth-service",
        })

    publisher_task = asyncio.create_task(_publish_soon())

    events = []
    async for item in sub_gen:
        assert item.errors is None
        payload = json.loads(item.data["incidentStream"])
        events.append(payload)

    await publisher_task

    assert len(events) == 2
    live_events = [e for e in events if e.get("heartbeat") is False]
    assert len(live_events) >= 1
    assert live_events[0]["status"] == "INCIDENT_CORRELATED"
    assert live_events[0]["event"]["incident_id"] == "inc-live-999"
