"""Incident listing and management router."""

from fastapi import APIRouter, Query
from sqlalchemy import select

from app.dependencies import DBSession
from app.models.db_models import Incident, Service
from app.models.schemas import IncidentSummary

router = APIRouter()


@router.get("/incidents", response_model=list[IncidentSummary])
def list_incidents(
    db: DBSession,
    limit: int = Query(50, ge=1, le=500),
    include_false_positives: bool = Query(False),
):
    """List recent correlated incidents."""
    stmt = select(Incident).order_by(Incident.timestamp_start.desc()).limit(limit)
    if not include_false_positives:
        stmt = stmt.where(Incident.was_false_positive.is_(False))

    incidents = db.scalars(stmt).all()
    summaries = []

    for inc in incidents:
        svc_name = None
        if inc.root_cause_service_id:
            svc = db.scalar(select(Service).where(Service.id == inc.root_cause_service_id))
            svc_name = svc.name if svc else None

        summaries.append(
            IncidentSummary(
                incident_id=inc.id,
                root_cause_service=svc_name,
                root_cause_service_id=inc.root_cause_service_id,
                root_cause_type=inc.root_cause_type,
                confidence=inc.confidence_at_detection,
                affected_services=[],
                is_multi_root_cause=inc.is_multi_root_cause,
                timestamp_start=inc.timestamp_start,
            )
        )

    return summaries
