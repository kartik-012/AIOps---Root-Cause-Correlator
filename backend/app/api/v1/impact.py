"""Impact Engine router — Business criticality and revenue risk scoring."""

import uuid
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.dependencies import DBSession
from app.graph.dependency_graph import DependencyGraph
from app.engines.impact_engine import ImpactEngine
from app.models.db_models import Incident, Service, ServiceDependency, Anomaly
from app.models.schemas import ImpactResponse

router = APIRouter()


@router.get("/impact/{incident_id}", response_model=ImpactResponse)
def get_impact(incident_id: uuid.UUID, db: DBSession):
    """Calculate business impact score for a specific incident."""
    inc = db.scalar(select(Incident).where(Incident.id == incident_id))
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    if not inc.root_cause_service_id:
        return ImpactResponse(impact_score=0.0, severity="low", revenue_weighted=True)

    services = db.scalars(select(Service)).all()
    deps = db.scalars(select(ServiceDependency)).all()
    nodes = [{"id": str(s.id), "name": s.name, "revenue_weight": s.revenue_weight} for s in services]
    edges = [{"from": str(d.from_service_id), "to": str(d.to_service_id)} for d in deps]
    dep_graph = DependencyGraph.from_nodes_and_edges(nodes, edges)

    # Determine severity from highest anomaly
    anomalies = db.scalars(select(Anomaly).where(Anomaly.incident_id == incident_id)).all()
    highest_severity = "high"
    if anomalies:
        for a in anomalies:
            if a.severity == "critical":
                highest_severity = "critical"
                break

    engine = ImpactEngine(dep_graph)
    assessment = engine.calculate_impact(
        service_id=str(inc.root_cause_service_id),
        severity=highest_severity,
    )

    return ImpactResponse(
        impact_score=assessment.impact_score,
        severity=assessment.severity_label,
        revenue_weighted=True,
    )
