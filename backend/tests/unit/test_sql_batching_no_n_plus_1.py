"""Unit tests verifying O(1) SQL query counts (zero N+1 query loops) across incidents, explain, and correlation routers."""

from datetime import datetime, timezone, timedelta
import uuid

from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker

from app.models.db_models import Base, Service, Incident, IncidentAffectedService, Anomaly
from app.api.v1.incidents import query_incidents_batch
from app.api.v1.explain import build_incident_explanation
from app.api.v1.correlation import query_incident_detail_joined, _persist_correlated_incident_sync
from app.engines.correlation_engine import CorrelatedIncident, AffectedServiceSummary, AnomalyEvent


def _make_tracked_sqlite_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    statements: list[str] = []

    @event.listens_for(engine, "before_cursor_execute")
    def _record_sql(conn, cursor, statement, parameters, context, executemany):
        statements.append(statement)

    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal, statements


def test_incidents_and_explain_and_detail_execute_constant_number_of_sql_queries():
    """Verify query_incidents_batch, build_incident_explanation, and query_incident_detail_joined execute O(1) SQL queries."""
    SessionLocal, statements = _make_tracked_sqlite_db()
    t0 = datetime(2026, 10, 12, 12, 0, 0, tzinfo=timezone.utc)

    with SessionLocal() as db:
        services = [
            Service(id=uuid.uuid4(), name=f"service-{i}", revenue_weight=float(i + 1))
            for i in range(8)
        ]
        db.add_all(services)
        db.flush()

        created_inc_ids: list[uuid.UUID] = []
        # Create 15 incidents, each with 4 affected services
        for idx in range(15):
            inc = Incident(
                id=uuid.uuid4(),
                root_cause_service_id=services[0].id,
                root_cause_type="db_pool_exhaustion",
                confidence_at_detection=0.92,
                is_multi_root_cause=False,
                was_false_positive=False,
                timestamp_start=t0 + timedelta(minutes=idx),
            )
            db.add(inc)
            db.flush()
            created_inc_ids.append(inc.id)

            for hop in range(1, 5):
                db.add(
                    IncidentAffectedService(
                        incident_id=inc.id,
                        service_id=services[hop].id,
                        propagation_order=hop,
                        affected_at=t0 + timedelta(minutes=idx, seconds=hop * 5),
                    )
                )

            db.add(
                Anomaly(
                    id=uuid.uuid4(),
                    service_id=services[0].id,
                    incident_id=inc.id,
                    metric_type="connection_pool",
                    z_score=4.8,
                    severity="critical",
                    detected_at=t0 + timedelta(minutes=idx),
                )
            )
        db.commit()

        # 1. Test query_incidents_batch across 15 incidents x 4 affected services = 60 rows
        statements.clear()
        summaries = query_incidents_batch(db, limit=50)
        assert len(summaries) == 15
        assert len(summaries[0].affected_services) == 4
        # Must execute exactly 2 SELECT statements (1 for Incident+Service, 1 for IncidentAffectedService+Service)
        select_stmts = [s for s in statements if s.strip().upper().startswith("SELECT")]
        assert len(select_stmts) == 2, f"Expected 2 SELECT statements, got {len(select_stmts)}"

        # 2. Test build_incident_explanation
        statements.clear()
        explanation = build_incident_explanation(db, created_inc_ids[0])
        assert explanation is not None
        assert "service-0" in explanation.summary
        assert "service-1" in explanation.summary
        select_stmts = [s for s in statements if s.strip().upper().startswith("SELECT")]
        assert len(select_stmts) == 2, f"Expected 2 SELECT statements in explain, got {len(select_stmts)}"

        # 3. Test query_incident_detail_joined
        statements.clear()
        detail = query_incident_detail_joined(db, created_inc_ids[0])
        assert detail is not None
        assert detail.root_cause_service_name == "service-0"
        assert len(detail.affected_services) == 4
        assert len(detail.anomalies) == 1
        select_stmts = [s for s in statements if s.strip().upper().startswith("SELECT")]
        assert len(select_stmts) == 3, f"Expected 3 SELECT statements in detail, got {len(select_stmts)}"


def test_persist_correlated_incident_uses_single_bulk_update_for_anomalies():
    """Verify _persist_correlated_incident_sync updates all linked anomalies with 1 bulk UPDATE instead of N SELECTs."""
    SessionLocal, statements = _make_tracked_sqlite_db()
    t0 = datetime(2026, 10, 12, 12, 0, 0, tzinfo=timezone.utc)

    with SessionLocal() as db:
        svc = Service(id=uuid.uuid4(), name="payment-service", revenue_weight=10.0)
        db.add(svc)
        db.flush()

        anom_events: list[AnomalyEvent] = []
        for i in range(6):
            a_row = Anomaly(
                id=uuid.uuid4(),
                service_id=svc.id,
                metric_type="latency_ms",
                z_score=3.5 + i * 0.2,
                severity="high",
                detected_at=t0 + timedelta(seconds=i),
            )
            db.add(a_row)
            db.flush()
            anom_events.append(
                AnomalyEvent(
                    id=str(a_row.id),
                    service_id=str(svc.id),
                    metric_type="latency_ms",
                    z_score=float(a_row.z_score),
                    severity="high",
                    detected_at=a_row.detected_at,
                )
            )
        db.commit()

        corr_inc = CorrelatedIncident(
            incident_id=str(uuid.uuid4()),
            root_cause_service_id=str(svc.id),
            root_cause_service_name="payment-service",
            root_cause_type="network_latency_injection",
            confidence=0.91,
            affected_service_ids=[],
            affected_services=[
                AffectedServiceSummary(
                    service_id=str(svc.id),
                    service_name="payment-service",
                    propagation_order=0,
                    affected_at=t0,
                )
            ],
            is_multi_root_cause=False,
            timestamp_start=t0,
            anomalies=anom_events,
            signature=[0.1, 0.2, 0.5, -0.5, 0.4, -0.5, 0.5],
        )

        statements.clear()
        inc_id, _, _ = _persist_correlated_incident_sync(db, corr_inc, 0.91)

        update_stmts = [s for s in statements if s.strip().upper().startswith("UPDATE")]
        select_stmts = [s for s in statements if s.strip().upper().startswith("SELECT")]
        assert len(update_stmts) == 1, f"Expected 1 bulk UPDATE statement, got {len(update_stmts)}"
        assert len(select_stmts) == 0, f"Expected 0 N+1 SELECT statements during persist, got {len(select_stmts)}"


def test_correlation_run_executes_at_most_3_select_queries():
    """Verify Gap #5 verification method: SQLAlchemy query counter test asserting <= 3 queries per correlation run."""
    from app.models.db_models import ServiceDependency
    from app.api.v1.correlation import _fetch_unclustered_and_correlate_sync

    SessionLocal, statements = _make_tracked_sqlite_db()
    t0 = datetime(2026, 10, 12, 12, 0, 0, tzinfo=timezone.utc)

    with SessionLocal() as db:
        s_pay = Service(id=uuid.uuid4(), name="payment-service", revenue_weight=10.0)
        s_ord = Service(id=uuid.uuid4(), name="order-service", revenue_weight=9.0)
        s_api = Service(id=uuid.uuid4(), name="api-gateway", revenue_weight=10.0)
        db.add_all([s_pay, s_ord, s_api])
        db.flush()

        db.add_all([
            ServiceDependency(from_service_id=s_api.id, to_service_id=s_ord.id),
            ServiceDependency(from_service_id=s_ord.id, to_service_id=s_pay.id),
        ])
        db.add_all([
            Anomaly(service_id=s_pay.id, metric_type="latency_ms", z_score=5.2, severity="critical", detected_at=t0),
            Anomaly(service_id=s_ord.id, metric_type="latency_ms", z_score=4.1, severity="critical", detected_at=t0 + timedelta(seconds=5)),
            Anomaly(service_id=s_api.id, metric_type="latency_ms", z_score=3.8, severity="high", detected_at=t0 + timedelta(seconds=10)),
        ])
        db.commit()

        statements.clear()
        correlated = _fetch_unclustered_and_correlate_sync(db)
        assert correlated is not None and len(correlated) == 1
        assert correlated[0].root_cause_service_id == str(s_pay.id)
        assert len(statements) <= 3, f"Expected <= 3 SQL queries per correlation run, got {len(statements)}"

