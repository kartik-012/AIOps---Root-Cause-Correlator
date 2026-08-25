"""Correlation Engine router — Clusters anomalies into incidents and identifies root causes."""

from datetime import datetime, timezone
import uuid
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.dependencies import DBSession
from app.graph.dependency_graph import DependencyGraph
from app.engines.correlation_engine import CorrelationEngine, AnomalyEvent
from app.models.db_models import Service, ServiceDependency, Anomaly, Incident, IncidentAffectedService
from app.models.schemas import CorrelationRunResponse, IncidentSummary, IncidentDetail, AffectedServiceOut, AnomalyOut
from app.api.v1.ws import broadcast_event

router = APIRouter()


def _build_db_dependency_graph(db: DBSession) -> DependencyGraph:
    """Build NetworkX dependency graph from database tables."""
    services = db.scalars(select(Service)).all()
    deps = db.scalars(select(ServiceDependency)).all()

    nodes = [{"id": str(s.id), "name": s.name, "revenue_weight": s.revenue_weight} for s in services]
    edges = [{"from": str(d.from_service_id), "to": str(d.to_service_id)} for d in deps]
    return DependencyGraph.from_nodes_and_edges(nodes, edges)


@router.post("/correlation/run", response_model=CorrelationRunResponse)
async def run_correlation(db: DBSession):
    """Trigger root cause correlation on all unclustered anomalies."""
    unclustered_anomalies = db.scalars(
        select(Anomaly).where(Anomaly.incident_id.is_(None)).order_by(Anomaly.detected_at.asc())
    ).all()

    if not unclustered_anomalies:
        return CorrelationRunResponse(incidents=[])

    dep_graph = _build_db_dependency_graph(db)
    engine = CorrelationEngine(dep_graph)

    engine_anomalies = [
        AnomalyEvent(
            id=str(a.id),
            service_id=str(a.service_id),
            metric_type=a.metric_type,
            z_score=a.z_score,
            severity=a.severity,
            detected_at=a.detected_at,
        )
        for a in unclustered_anomalies
    ]

    correlated = engine.correlate(engine_anomalies)
    summaries: list[IncidentSummary] = []

    for inc in correlated:
        root_svc_uuid = uuid.UUID(inc.root_cause_service_id) if inc.root_cause_service_id else None

        db_incident = Incident(
            timestamp_start=inc.timestamp_start,
            root_cause_service_id=root_svc_uuid,
            root_cause_type=inc.root_cause_type,
            confidence_at_detection=inc.confidence,
            is_multi_root_cause=inc.is_multi_root_cause,
            anomaly_signature=inc.signature if len(inc.signature) == 7 else None,
        )
        db.add(db_incident)
        db.commit()
        db.refresh(db_incident)

        # Record affected services in propagation order
        affected_names = []
        for aff in inc.affected_services:
            aff_uuid = uuid.UUID(aff.service_id)
            ias = IncidentAffectedService(
                incident_id=db_incident.id,
                service_id=aff_uuid,
                propagation_order=aff.propagation_order,
                affected_at=aff.affected_at,
            )
            db.add(ias)
            if aff.service_name and aff.service_id != inc.root_cause_service_id:
                affected_names.append(aff.service_name)

        # Link anomalies to this incident
        for a_event in inc.anomalies:
            a_db = db.scalar(select(Anomaly).where(Anomaly.id == uuid.UUID(a_event.id)))
            if a_db:
                a_db.incident_id = db_incident.id

        db.commit()

        summaries.append(
            IncidentSummary(
                incident_id=db_incident.id,
                root_cause_service=inc.root_cause_service_name,
                root_cause_service_id=root_svc_uuid,
                root_cause_type=inc.root_cause_type,
                confidence=inc.confidence,
                affected_services=affected_names,
                is_multi_root_cause=inc.is_multi_root_cause,
                timestamp_start=inc.timestamp_start,
            )
        )

        # Broadcast live incident event over WebSocket
        await broadcast_event({
            "type": "incident_correlated",
            "incident_id": str(db_incident.id),
            "root_cause_service": inc.root_cause_service_name,
            "root_cause_type": inc.root_cause_type,
            "confidence": inc.confidence,
            "is_multi_root_cause": inc.is_multi_root_cause,
            "affected_services": affected_names,
            "timestamp": inc.timestamp_start.isoformat(),
        })

    return CorrelationRunResponse(incidents=summaries)


@router.get("/correlation/incidents/{incident_id}", response_model=IncidentDetail)
def get_incident(incident_id: uuid.UUID, db: DBSession):
    """Retrieve full incident detail including root cause, timeline, affected services, and anomalies."""
    inc = db.scalar(select(Incident).where(Incident.id == incident_id))
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    root_svc_name = None
    if inc.root_cause_service_id:
        svc = db.scalar(select(Service).where(Service.id == inc.root_cause_service_id))
        root_svc_name = svc.name if svc else None

    # Affected services in propagation order
    ias_list = db.scalars(
        select(IncidentAffectedService)
        .where(IncidentAffectedService.incident_id == incident_id)
        .order_by(IncidentAffectedService.propagation_order.asc())
    ).all()

    affected_out = []
    for item in ias_list:
        s = db.scalar(select(Service).where(Service.id == item.service_id))
        affected_out.append(
            AffectedServiceOut(
                service_id=item.service_id,
                service_name=s.name if s else str(item.service_id),
                propagation_order=item.propagation_order,
                affected_at=item.affected_at,
            )
        )

    # Linked anomalies
    anomalies = db.scalars(select(Anomaly).where(Anomaly.incident_id == incident_id)).all()
    anomalies_out = [
        AnomalyOut(
            id=a.id,
            service_id=a.service_id,
            metric_type=a.metric_type,
            z_score=a.z_score,
            severity=a.severity,
            detected_at=a.detected_at,
            incident_id=a.incident_id,
        )
        for a in anomalies
    ]

    sig_list = [float(x) for x in inc.anomaly_signature] if inc.anomaly_signature is not None else None

    return IncidentDetail(
        id=inc.id,
        timestamp_start=inc.timestamp_start,
        timestamp_end=inc.timestamp_end,
        root_cause_service_id=inc.root_cause_service_id,
        root_cause_service_name=root_svc_name,
        root_cause_type=inc.root_cause_type,
        confidence_at_detection=inc.confidence_at_detection,
        is_multi_root_cause=inc.is_multi_root_cause,
        was_false_positive=inc.was_false_positive,
        anomaly_signature=sig_list,
        affected_services=affected_out,
        anomalies=anomalies_out,
    )
