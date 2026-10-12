"""Integrations router — Slack/Discord alerting, LLM executive post-mortems, and OpenTelemetry receiver."""

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator
from sqlalchemy import select

from app.dependencies import DBSession
from app.models.db_models import Incident, Service, Anomaly, IncidentAffectedService
from app.services.slack_notifier import SlackNotifier, WebhookSecurityError, validate_webhook_url
from app.services.llm_report_generator import LLMReportGenerator, AnomalyEvidenceItem
from app.engines.detection_engine import DetectionEngine
from app.api.v1.detection import get_detection_engine

router = APIRouter()
_slack_notifier = SlackNotifier()
_report_generator = LLMReportGenerator()


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


class OtelPayload(BaseModel):
    spans: list[OtelSpan] = []


@router.post("/integrations/slack/webhook")
async def send_slack_alert(payload: SlackAlertRequest, db: DBSession):
    """Dispatch a rich incident correlation card to a verified Slack/Discord webhook."""
    # Pre-validate user-supplied webhook URL against SSRF (including DNS resolution) before any DB or network work
    if payload.webhook_url and payload.webhook_url.strip():
        try:
            validate_webhook_url(payload.webhook_url)
        except WebhookSecurityError as exc:
            raise HTTPException(status_code=422, detail=str(exc)) from exc

    inc = None
    try:
        inc_uuid = uuid.UUID(payload.incident_id)
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
        raise HTTPException(status_code=400, detail=str(exc)) from exc

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


@router.post("/telemetry/otel")
def ingest_opentelemetry(payload: OtelPayload, db: DBSession):
    """Ingest OpenTelemetry spans in a single batched DB transaction (eliminates per-span N+1 queries and commits)."""
    if not payload.spans:
        return {"status": "processed", "spans_count": 0, "results": []}

    engine = get_detection_engine()
    results = []

    unique_names = list({span.service_name for span in payload.spans if span.service_name})
    existing_svcs = db.scalars(select(Service).where(Service.name.in_(unique_names))).all()
    svc_by_name = {s.name: s for s in existing_svcs}

    # Create any missing services in a single flush
    for sname in unique_names:
        if sname not in svc_by_name:
            new_svc = Service(name=sname, revenue_weight=5.0)
            db.add(new_svc)
            svc_by_name[sname] = new_svc
    db.flush()

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

        results.append({
            "service": span.service_name,
            "duration_ms": span.duration_ms,
            "anomaly_detected": res.is_anomaly,
            "z_score": res.z_score,
        })

    db.commit()

    return {
        "status": "processed",
        "spans_count": len(payload.spans),
        "results": results,
    }
