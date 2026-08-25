"""Integrations router — Slack/Discord alerting, LLM executive post-mortems, and OpenTelemetry receiver."""

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import select

from app.dependencies import DBSession
from app.models.db_models import Incident, Service, Anomaly, IncidentAffectedService
from app.services.slack_notifier import SlackNotifier
from app.services.llm_report_generator import LLMReportGenerator
from app.engines.detection_engine import DetectionEngine
from app.api.v1.detection import get_detection_engine

router = APIRouter()
_slack_notifier = SlackNotifier()
_report_generator = LLMReportGenerator()


class SlackAlertRequest(BaseModel):
    incident_id: str = "inc-default"
    webhook_url: str | None = None


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
    """Dispatch a rich incident correlation card to a Slack/Discord webhook."""
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

        ias = db.scalars(select(IncidentAffectedService).where(IncidentAffectedService.incident_id == inc.id)).all()
        if ias:
            affected_names = []
            for item in ias:
                s = db.scalar(select(Service).where(Service.id == item.service_id))
                if s and s.name != root_svc_name:
                    affected_names.append(s.name)

    result = await _slack_notifier.send_incident_alert(
        incident_id=payload.incident_id,
        root_cause_service=root_svc_name,
        root_cause_type=root_type,
        confidence=confidence,
        affected_services=affected_names,
        impact_score=impact_val,
        webhook_url=payload.webhook_url,
    )
    return result


@router.post("/integrations/llm/post-mortem")
def generate_post_mortem_report(payload: PostMortemRequest, db: DBSession):
    """Generate an AI-powered Executive Post-Mortem and Root Cause Analysis document."""
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
    start_time = datetime.now(timezone.utc)

    if inc:
        root_type = inc.root_cause_type or root_type
        confidence = inc.confidence_at_detection or confidence
        start_time = inc.timestamp_start or start_time
        if inc.root_cause_service_id:
            svc = db.scalar(select(Service).where(Service.id == inc.root_cause_service_id))
            if svc:
                root_svc_name = svc.name

        ias = db.scalars(select(IncidentAffectedService).where(IncidentAffectedService.incident_id == inc.id)).all()
        if ias:
            affected_names = []
            for item in ias:
                s = db.scalar(select(Service).where(Service.id == item.service_id))
                if s and s.name != root_svc_name:
                    affected_names.append(s.name)

    report = _report_generator.generate_post_mortem(
        incident_id=payload.incident_id,
        root_cause_service=root_svc_name,
        root_cause_type=root_type,
        confidence=confidence,
        affected_services=affected_names,
        impact_score=impact_val,
        timestamp_start=start_time,
    )
    return report


@router.post("/telemetry/otel")
async def ingest_opentelemetry(payload: OtelPayload, db: DBSession):
    """Ingest OpenTelemetry spans, translate to metrics, and feed into EWMA detection engine."""
    engine = get_detection_engine()
    results = []

    for span in payload.spans:
        svc = db.scalar(select(Service).where(Service.name == span.service_name))
        if not svc:
            svc = Service(name=span.service_name, revenue_weight=5.0)
            db.add(svc)
            db.commit()
            db.refresh(svc)

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
            db.commit()

        results.append({
            "service": span.service_name,
            "duration_ms": span.duration_ms,
            "anomaly_detected": res.is_anomaly,
            "z_score": res.z_score,
        })

    return {
        "status": "processed",
        "spans_count": len(payload.spans),
        "results": results,
    }
