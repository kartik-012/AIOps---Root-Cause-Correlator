"""Integrations router — Slack/Discord alerting, LLM executive post-mortems, and OpenTelemetry receiver."""

from collections import OrderedDict
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import select

from app.dependencies import DBSession
from app.models.db_models import (
    Incident,
    Service,
    ServiceDependency,
    Anomaly,
    IncidentAffectedService,
    DeploymentEvent,
)
from app.services.slack_notifier import SlackNotifier, WebhookSecurityError, validate_webhook_url
from app.services.llm_report_generator import LLMReportGenerator, AnomalyEvidenceItem
from app.engines.detection_engine import DetectionEngine
from app.api.v1.detection import get_detection_engine

router = APIRouter()
_slack_notifier = SlackNotifier()
_report_generator = LLMReportGenerator()
_MAX_SPAN_INDEX_SIZE = 5000
_span_service_index: OrderedDict[tuple[str, str], str] = OrderedDict()


class SlackAlertRequest(BaseModel):
    incident_id: str = "inc-default"
    webhook_url: str | None = None

    @field_validator("webhook_url")
    @classmethod
    def _validate_ssrf_safe_webhook(cls, v: str | None) -> str | None:
        if v is not None and v.strip():
            try:
                validate_webhook_url(v, resolve_dns=False)
            except WebhookSecurityError as exc:
                raise ValueError(str(exc)) from exc
        return v


class PostMortemRequest(BaseModel):
    incident_id: str = "inc-default"


class OtelSpan(BaseModel):
    name: str
    service_name: str
    duration_ms: float
    status_code: str = "OK"  # 'OK', 'ERROR'
    timestamp: datetime | None = None
    trace_id: str | None = None
    span_id: str | None = None
    parent_span_id: str | None = None
    peer_service: str | None = None


class OtelPayload(BaseModel):
    spans: list[OtelSpan] = []


class DeploymentEventRequest(BaseModel):
    service_name: str
    git_sha: str
    config_version: str | None = None
    deployed_by: str | None = "ci-cd-pipeline"
    environment: str = "production"
    deployed_at: datetime | None = None



def _resolve_slack_incident_context_sync(
    db,
    incident_id: str,
) -> tuple[str, str, float, list[str], float]:
    inc = None
    try:
        inc_uuid = uuid.UUID(incident_id)
        inc = db.scalar(select(Incident).where(Incident.id == inc_uuid))
    except Exception:
        pass

    root_svc_name = "Payment Service"
    root_type = "db_connection_exhaustion"
    confidence = 0.94
    affected_names = ["Order Service", "API Gateway"]
    impact_val = 87.0

    if inc:
        root_type = inc.root_cause_type or root_type
        confidence = inc.confidence_at_detection or confidence
        if inc.root_cause_service_id:
            svc = db.scalar(select(Service).where(Service.id == inc.root_cause_service_id))
            if svc:
                root_svc_name = svc.name

        joined_ias = db.execute(
            select(IncidentAffectedService, Service)
            .join(Service, IncidentAffectedService.service_id == Service.id)
            .where(IncidentAffectedService.incident_id == inc.id)
            .order_by(IncidentAffectedService.propagation_order.asc())
        ).all()
        if joined_ias:
            affected_names = [
                svc_row.name
                for _, svc_row in joined_ias
                if svc_row.name != root_svc_name
            ]

    return root_svc_name, root_type, confidence, affected_names, impact_val


@router.post("/integrations/slack/webhook")
async def send_slack_alert(payload: SlackAlertRequest, db: DBSession):
    """Dispatch a rich incident correlation card to a verified Slack/Discord webhook."""
    from fastapi.concurrency import run_in_threadpool

    # Pre-validate user-supplied webhook URL against SSRF (including DNS resolution) before any DB or network work
    if payload.webhook_url and payload.webhook_url.strip():
        try:
            validate_webhook_url(payload.webhook_url)
        except WebhookSecurityError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    root_svc_name, root_type, confidence, affected_names, impact_val = await run_in_threadpool(
        _resolve_slack_incident_context_sync,
        db,
        payload.incident_id,
    )

    try:
        result = await _slack_notifier.send_incident_alert(
            incident_id=payload.incident_id,
            root_cause_service=root_svc_name,
            root_cause_type=root_type,
            confidence=confidence,
            affected_services=affected_names,
            impact_score=impact_val,
            webhook_url=payload.webhook_url,
        )
    except WebhookSecurityError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    return result


@router.post("/integrations/llm/post-mortem")
def generate_post_mortem_report(payload: PostMortemRequest, db: DBSession):
    """Generate an evidence-grounded Executive Post-Mortem and Root Cause Analysis document."""
    inc = None
    try:
        inc_uuid = uuid.UUID(payload.incident_id)
        inc = db.scalar(select(Incident).where(Incident.id == inc_uuid))
    except Exception:
        pass

    root_svc_name = "payment-service"
    root_type = "db_connection_exhaustion"
    confidence = 0.94
    affected_names: list[str] = ["order-service", "api-gateway"]
    impact_val = 87.0
    start_time = datetime.now(timezone.utc)
    detected_time: datetime | None = None
    end_time: datetime | None = None
    anomaly_evidence: list[AnomalyEvidenceItem] = []
    total_revenue_weight: float | None = None

    if inc:
        root_type = inc.root_cause_type or root_type
        confidence = inc.confidence_at_detection or confidence
        start_time = inc.timestamp_start or start_time
        detected_time = inc.created_at
        end_time = inc.timestamp_end
        weights_accum = 0.0

        if inc.root_cause_service_id:
            svc = db.scalar(select(Service).where(Service.id == inc.root_cause_service_id))
            if svc:
                root_svc_name = svc.name
                weights_accum += float(svc.revenue_weight or 0.0)

        # Single SQL JOIN to fetch all affected services and their revenue weights (eliminates N+1)
        joined_ias = db.execute(
            select(IncidentAffectedService, Service)
            .join(Service, IncidentAffectedService.service_id == Service.id)
            .where(IncidentAffectedService.incident_id == inc.id)
            .order_by(IncidentAffectedService.propagation_order.asc())
        ).all()
        if joined_ias:
            affected_names = []
            for _, svc_row in joined_ias:
                if svc_row.name != root_svc_name:
                    affected_names.append(svc_row.name)
                    weights_accum += float(svc_row.revenue_weight or 0.0)

        if weights_accum > 0.0:
            total_revenue_weight = weights_accum

        # Single SQL JOIN to fetch verified anomaly records for citation grounding
        joined_anoms = db.execute(
            select(Anomaly, Service.name)
            .join(Service, Anomaly.service_id == Service.id)
            .where(Anomaly.incident_id == inc.id)
            .order_by(Anomaly.detected_at.asc())
        ).all()
        for anom_row, svc_name in joined_anoms:
            anomaly_evidence.append(
                AnomalyEvidenceItem(
                    anomaly_id=str(anom_row.id),
                    service_name=svc_name,
                    metric_type=anom_row.metric_type,
                    z_score=float(anom_row.z_score),
                    severity=anom_row.severity,
                    detected_at=anom_row.detected_at,
                )
            )

    report = _report_generator.generate_post_mortem(
        incident_id=payload.incident_id,
        root_cause_service=root_svc_name,
        root_cause_type=root_type,
        confidence=confidence,
        affected_services=affected_names,
        impact_score=impact_val,
        timestamp_start=start_time,
        timestamp_detected=detected_time,
        timestamp_end=end_time,
        anomalies=anomaly_evidence if anomaly_evidence else None,
        total_revenue_weight=total_revenue_weight,
    )
    return report


def _record_span_in_index(trace_id: str | None, span_id: str | None, service_name: str) -> None:
    if not span_id or not service_name:
        return
    key = (trace_id or "default", span_id)
    _span_service_index[key] = service_name
    _span_service_index.move_to_end(key)
    while len(_span_service_index) > _MAX_SPAN_INDEX_SIZE:
        _span_service_index.popitem(last=False)


@router.post("/telemetry/otel")
def ingest_opentelemetry(payload: OtelPayload, db: DBSession):
    """Ingest OpenTelemetry spans in a single batched DB transaction and dynamically discover
    directed service dependency edges (`caller -> callee`) from parent-child span links and `peer_service`.
    """
    if not payload.spans:
        return {
            "status": "processed",
            "spans_count": 0,
            "results": [],
            "discovered_dependencies": [],
        }

    engine = get_detection_engine()
    results = []

    unique_names_set: set[str] = set()
    for span in payload.spans:
        if span.service_name:
            unique_names_set.add(span.service_name)
        if span.peer_service:
            unique_names_set.add(span.peer_service)
        _record_span_in_index(span.trace_id, span.span_id, span.service_name)

    unique_names = list(unique_names_set)
    existing_svcs = db.scalars(select(Service).where(Service.name.in_(unique_names))).all()
    svc_by_name = {s.name: s for s in existing_svcs}

    # Create any missing services in a single flush
    for sname in unique_names:
        if sname not in svc_by_name:
            new_svc = Service(name=sname, revenue_weight=5.0)
            db.add(new_svc)
            svc_by_name[sname] = new_svc
    db.flush()

    # Track directed edges (caller_name, callee_name) -> latest timestamp
    discovered_edge_times: dict[tuple[str, str], datetime] = {}

    for span in payload.spans:
        svc = svc_by_name[span.service_name]
        ts = span.timestamp or datetime.now(timezone.utc)
        res = engine.process_metric(str(svc.id), "latency_ms", span.duration_ms, ts)

        if res.is_anomaly or span.status_code == "ERROR":
            anom = Anomaly(
                service_id=svc.id,
                metric_type="latency_ms" if res.is_anomaly else "error_rate",
                z_score=res.z_score if res.is_anomaly else 4.0,
                severity=res.severity if res.is_anomaly else "high",
                detected_at=ts,
            )
            db.add(anom)

        # 1. Parent-Child Span Linking: parent_span_id belongs to caller_service, current span is callee_service
        if span.parent_span_id:
            parent_svc_name = _span_service_index.get((span.trace_id or "default", span.parent_span_id))
            if parent_svc_name and parent_svc_name != span.service_name:
                if parent_svc_name not in svc_by_name:
                    p_svc = db.scalar(select(Service).where(Service.name == parent_svc_name))
                    if p_svc is None:
                        p_svc = Service(name=parent_svc_name, revenue_weight=5.0)
                        db.add(p_svc)
                        db.flush()
                    svc_by_name[parent_svc_name] = p_svc
                discovered_edge_times[(parent_svc_name, span.service_name)] = ts

        # 2. Explicit peer_service attribute: current span's service calls peer_service
        if span.peer_service and span.peer_service != span.service_name:
            discovered_edge_times[(span.service_name, span.peer_service)] = ts

        results.append({
            "service": span.service_name,
            "duration_ms": span.duration_ms,
            "anomaly_detected": res.is_anomaly,
            "z_score": res.z_score,
        })

    # Upsert discovered directed edges into ServiceDependency with last_seen_at
    discovered_dependencies: list[dict] = []
    if discovered_edge_times:
        involved_ids = [s.id for s in svc_by_name.values()]
        existing_deps = db.scalars(
            select(ServiceDependency).where(
                ServiceDependency.from_service_id.in_(involved_ids),
                ServiceDependency.to_service_id.in_(involved_ids),
            )
        ).all()
        dep_by_pair = {(d.from_service_id, d.to_service_id): d for d in existing_deps}

        for (caller_name, callee_name), seen_ts in discovered_edge_times.items():
            caller_id = svc_by_name[caller_name].id
            callee_id = svc_by_name[callee_name].id
            pair_key = (caller_id, callee_id)
            if pair_key in dep_by_pair:
                dep_by_pair[pair_key].last_seen_at = seen_ts
                is_new = False
            else:
                new_dep = ServiceDependency(
                    from_service_id=caller_id,
                    to_service_id=callee_id,
                    last_seen_at=seen_ts,
                )
                db.add(new_dep)
                dep_by_pair[pair_key] = new_dep
                is_new = True

            discovered_dependencies.append({
                "from_service": caller_name,
                "to_service": callee_name,
                "is_new_edge": is_new,
                "last_seen_at": seen_ts.isoformat(),
            })

    db.commit()

    return {
        "status": "processed",
        "spans_count": len(payload.spans),
        "results": results,
        "discovered_dependencies": discovered_dependencies,
    }


@router.post("/deployments")
def ingest_deployment_event(payload: DeploymentEventRequest, db: DBSession):
    """Ingest a Git SHA or config rollout change event for Change-Event Correlation (Differentiator #5)."""
    svc = db.scalar(select(Service).where(Service.name == payload.service_name))
    if svc is None:
        svc = Service(name=payload.service_name, revenue_weight=5.0)
        db.add(svc)
        db.flush()

    deployed_ts = payload.deployed_at or datetime.now(timezone.utc)
    dep_event = DeploymentEvent(
        service_id=svc.id,
        git_sha=payload.git_sha,
        config_version=payload.config_version,
        deployed_by=payload.deployed_by,
        environment=payload.environment,
        deployed_at=deployed_ts,
    )
    db.add(dep_event)
    db.commit()

    return {
        "status": "recorded",
        "deployment_id": str(dep_event.id),
        "service_id": str(svc.id),
        "service_name": svc.name,
        "git_sha": dep_event.git_sha,
        "config_version": dep_event.config_version,
        "deployed_by": dep_event.deployed_by,
        "environment": dep_event.environment,
        "deployed_at": deployed_ts.isoformat(),
    }


@router.get("/deployments")
def list_deployment_events(db: DBSession, limit: int = 20):
    """List recent deployment events across services."""
    rows = db.execute(
        select(DeploymentEvent, Service.name)
        .join(Service, DeploymentEvent.service_id == Service.id)
        .order_by(DeploymentEvent.deployed_at.desc())
        .limit(max(1, min(limit, 100)))
    ).all()
    return {
        "deployments": [
            {
                "deployment_id": str(ev.id),
                "service_id": str(ev.service_id),
                "service_name": svc_name,
                "git_sha": ev.git_sha,
                "config_version": ev.config_version,
                "deployed_by": ev.deployed_by,
                "environment": ev.environment,
                "deployed_at": ev.deployed_at.isoformat(),
            }
            for ev, svc_name in rows
        ]
    }


