"""Counterfactual Engine router — What-if incident re-simulation."""

import uuid
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.dependencies import DBSession
from app.graph.dependency_graph import DependencyGraph
from app.engines.correlation_engine import AnomalyEvent
from app.engines.counterfactual_engine import CounterfactualEngine
from app.models.db_models import Incident, Anomaly, Service, ServiceDependency, IncidentAffectedService
from app.models.schemas import CounterfactualRequest, CounterfactualResponse

router = APIRouter()


@router.post("/counterfactual/simulate", response_model=CounterfactualResponse)
def simulate_counterfactual(payload: CounterfactualRequest, db: DBSession):
    """Re-simulate an incident under a hypothetical parameter modification."""
    inc = db.scalar(select(Incident).where(Incident.id == payload.incident_id))
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    # Build graph
    services = db.scalars(select(Service)).all()
    deps = db.scalars(select(ServiceDependency)).all()
    svc_map = {s.name: str(s.id) for s in services}
    id_to_name = {str(s.id): s.name for s in services}

    nodes = [{"id": str(s.id), "name": s.name, "revenue_weight": s.revenue_weight} for s in services]
    edges = [{"from": str(d.from_service_id), "to": str(d.to_service_id)} for d in deps]
    dep_graph = DependencyGraph.from_nodes_and_edges(nodes, edges)

    # Load incident anomalies
    anomalies = db.scalars(select(Anomaly).where(Anomaly.incident_id == payload.incident_id)).all()
    engine_anomalies = [
        AnomalyEvent(
            id=str(a.id),
            service_id=str(a.service_id),
            metric_type=a.metric_type,
            z_score=a.z_score,
            severity=a.severity,
            detected_at=a.detected_at,
        )
        for a in anomalies
    ]

    target_svc_name = payload.modified_parameter.service
    target_svc_id = svc_map.get(target_svc_name, target_svc_name)

    engine = CounterfactualEngine(dep_graph)
    sim = engine.simulate(
        original_anomalies=engine_anomalies,
        modified_service_id=target_svc_id,
        modified_metric=payload.modified_parameter.metric,
        capped_value=payload.modified_parameter.capped_at,
    )

    orig_names = [id_to_name.get(sid, sid) for sid in sim.original_affected_services]
    sim_names = [id_to_name.get(sid, sid) for sid in sim.simulated_affected_services]

    return CounterfactualResponse(
        would_cascade=sim.would_cascade,
        original_affected_services=orig_names,
        simulated_affected_services=sim_names,
    )
