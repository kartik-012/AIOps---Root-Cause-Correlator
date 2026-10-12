"""Celery application configuration and background SRE worker tasks.

Defines executable background tasks for:
1. Scheduled anomaly correlation sweeps (`run_scheduled_correlation_sweep`).
2. Asynchronous executive post-mortem synthesis (`generate_incident_post_mortem_task`).
3. Stale EWMA state & raw metric retention pruning (`prune_telemetry_retention_task`).
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
import logging
from typing import Any

from celery import Celery
from sqlalchemy import select, delete

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

celery_app = Celery(
    "aiops_tasks",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.REDIS_URL,
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    beat_schedule={
        "correlate-unlinked-anomalies-every-30s": {
            "task": "aiops.tasks.run_scheduled_correlation_sweep",
            "schedule": 30.0,
        },
        "prune-telemetry-retention-hourly": {
            "task": "aiops.tasks.prune_telemetry_retention",
            "schedule": 3600.0,
        },
    },
)


@celery_app.task(name="aiops.tasks.run_scheduled_correlation_sweep")
def run_scheduled_correlation_sweep(window_minutes: int = 5) -> dict[str, Any]:
    """Correlate any unlinked anomalies detected within the last `window_minutes`."""
    from app.dependencies import get_session_factory
    from app.models.db_models import Anomaly, Service, ServiceDependency, Incident
    from app.graph.dependency_graph import DependencyGraph
    from app.engines.correlation_engine import CorrelationEngine, AnomalyEvent

    factory = get_session_factory(settings)
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=window_minutes)

    with factory() as db:
        unlinked = db.scalars(
            select(Anomaly)
            .where(Anomaly.incident_id.is_(None), Anomaly.detected_at >= cutoff)
            .order_by(Anomaly.detected_at.asc())
        ).all()

        if not unlinked:
            return {"status": "idle", "unlinked_anomalies": 0, "incidents_created": 0}

        services = db.scalars(select(Service)).all()
        deps = db.scalars(select(ServiceDependency)).all()
        nodes = [{"id": str(s.id), "name": s.name, "revenue_weight": float(s.revenue_weight or 1.0)} for s in services]
        edges = [{"from": str(d.from_service_id), "to": str(d.to_service_id)} for d in deps]

        dep_graph = DependencyGraph.from_nodes_and_edges(nodes, edges)
        corr_engine = CorrelationEngine(dep_graph)

        events = [
            AnomalyEvent(
                id=str(a.id),
                service_id=str(a.service_id),
                metric_type=a.metric_type,
                z_score=float(a.z_score),
                severity=a.severity,
                detected_at=a.detected_at,
            )
            for a in unlinked
        ]
        correlated = corr_engine.correlate(events)
        created = 0
        for inc in correlated:
            db_inc = Incident(
                root_cause_service_id=inc.root_cause_service_id,
                root_cause_type=inc.root_cause_type,
                confidence_at_detection=inc.confidence,
                is_multi_root_cause=inc.is_multi_root_cause,
                timestamp_start=inc.timestamp_start,
                anomaly_signature=inc.signature,
            )
            db.add(db_inc)
            db.flush()
            created += 1

        db.commit()
        return {
            "status": "completed",
            "unlinked_anomalies": len(unlinked),
            "incidents_created": created,
        }


@celery_app.task(name="aiops.tasks.generate_incident_post_mortem")
def generate_incident_post_mortem_task(
    incident_id: str,
    root_cause_service: str,
    root_cause_type: str,
    confidence: float,
    affected_services: list[str],
    impact_score: float,
) -> dict[str, Any]:
    """Generate an evidence-grounded Executive Post-Mortem asynchronously in a Celery worker."""
    from app.services.llm_report_generator import LLMReportGenerator

    generator = LLMReportGenerator()
    return generator.generate_post_mortem(
        incident_id=incident_id,
        root_cause_service=root_cause_service,
        root_cause_type=root_cause_type,
        confidence=confidence,
        affected_services=affected_services,
        impact_score=impact_score,
        timestamp_start=datetime.now(timezone.utc),
    )


@celery_app.task(name="aiops.tasks.prune_telemetry_retention")
def prune_telemetry_retention_task(retention_hours: int = 24) -> dict[str, Any]:
    """Delete raw telemetry points older than `retention_hours` to bound table bloat."""
    from app.dependencies import get_session_factory
    from app.models.db_models import MetricRaw

    factory = get_session_factory(settings)
    cutoff = datetime.now(timezone.utc) - timedelta(hours=retention_hours)
    with factory() as db:
        res = db.execute(delete(MetricRaw).where(MetricRaw.recorded_at < cutoff))
        db.commit()
        deleted = int(res.rowcount or 0)
    return {"status": "pruned", "deleted_raw_metrics": deleted, "cutoff": cutoff.isoformat()}
