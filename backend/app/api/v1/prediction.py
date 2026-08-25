"""Prediction Engine router — Forecasts blast radius and cascade propagation."""

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.dependencies import DBSession
from app.graph.dependency_graph import DependencyGraph
from app.engines.prediction_engine import PredictionEngine
from app.models.db_models import Incident, Service, ServiceDependency, IncidentAffectedService, BlastRadiusPrediction
from app.models.schemas import BlastRadiusResponse, BlastRadiusPredictionOut
from app.api.v1.ws import broadcast_event

router = APIRouter()


@router.get("/prediction/blast-radius/{incident_id}", response_model=BlastRadiusResponse)
async def get_blast_radius(incident_id: uuid.UUID, db: DBSession):
    """Predict blast radius and estimated time of cascade propagation."""
    inc = db.scalar(select(Incident).where(Incident.id == incident_id))
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    if not inc.root_cause_service_id:
        return BlastRadiusResponse(predictions=[])

    # Build graph
    services = db.scalars(select(Service)).all()
    deps = db.scalars(select(ServiceDependency)).all()
    nodes = [{"id": str(s.id), "name": s.name, "revenue_weight": s.revenue_weight} for s in services]
    edges = [{"from": str(d.from_service_id), "to": str(d.to_service_id)} for d in deps]
    dep_graph = DependencyGraph.from_nodes_and_edges(nodes, edges)

    # Already affected services
    ias = db.scalars(select(IncidentAffectedService).where(IncidentAffectedService.incident_id == incident_id)).all()
    already_affected = [str(a.service_id) for a in ias]

    engine = PredictionEngine(dep_graph)
    result = engine.predict_blast_radius(
        incident_id=str(incident_id),
        root_cause_service_id=str(inc.root_cause_service_id),
        already_affected_service_ids=already_affected,
    )

    out_items = []
    for p in result.predictions:
        p_uuid = uuid.UUID(p.service_id)
        # Store prediction in DB
        db_pred = BlastRadiusPrediction(
            incident_id=incident_id,
            predicted_service_id=p_uuid,
            predicted_eta_seconds=p.eta_seconds,
            confidence=p.confidence,
        )
        db.add(db_pred)

        out_items.append(
            BlastRadiusPredictionOut(
                service=p.service_name,
                service_id=p_uuid,
                eta_seconds=p.eta_seconds,
                confidence=p.confidence,
            )
        )

    db.commit()

    # Broadcast WebSocket update
    await broadcast_event({
        "type": "blast_radius_updated",
        "incident_id": str(incident_id),
        "predictions": [
            {"service": p.service_name, "eta_seconds": p.eta_seconds, "confidence": p.confidence}
            for p in result.predictions
        ],
    })

    return BlastRadiusResponse(predictions=out_items)
