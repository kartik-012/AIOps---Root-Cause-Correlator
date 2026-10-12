"""Suppression Engine router — False-positive checking and historical pattern labeling."""

import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.dependencies import DBSession
from app.engines.suppression_engine import SuppressionEngine
from app.models.db_models import Incident, Anomaly, Suppression
from app.models.schemas import SuppressionCheckRequest, SuppressionCheckResponse, MarkFalsePositiveResponse

router = APIRouter()

_suppression_engine = SuppressionEngine(similarity_threshold=0.85)


def get_suppression_engine(db: DBSession) -> SuppressionEngine:
    """Sync false-positive incidents from DB into memory cache."""
    fps = db.scalars(select(Incident).where(Incident.was_false_positive.is_(True))).all()
    _suppression_engine.clear_templates()
    for fp in fps:
        if fp.anomaly_signature is not None:
            sig = [float(x) for x in fp.anomaly_signature]
            tag = fp.learned_pattern_tag or fp.root_cause_type or "benign_pattern"
            _suppression_engine.register_false_positive(str(fp.id), sig, tag)
    return _suppression_engine


@router.post("/suppression/check", response_model=SuppressionCheckResponse)
def check_suppression(payload: SuppressionCheckRequest, db: DBSession):
    """Check a 7-dim anomaly signature against known false positives via pgvector SQL (with memory fallback)."""
    engine = get_suppression_engine(db)
    decision = engine.evaluate(payload.anomaly_signature, db=db)

    matched_uuid = uuid.UUID(decision.matched_incident_id) if decision.matched_incident_id else None

    # If suppressed, log into DB suppressions table (never silently drop)
    if decision.should_suppress and matched_uuid:
        # Create a mock anomaly record if needed or reference recent anomaly
        recent_a = db.scalar(select(Anomaly).order_by(Anomaly.detected_at.desc()))
        if recent_a:
            supp = Suppression(
                triggering_anomaly_id=recent_a.id,
                matched_incident_id=matched_uuid,
                similarity_score=decision.similarity_score,
                suppressed_at=datetime.now(timezone.utc),
            )
            db.add(supp)
            db.commit()

    return SuppressionCheckResponse(
        suppress=decision.should_suppress,
        matched_incident_id=matched_uuid,
        similarity=decision.similarity_score,
    )


from pydantic import BaseModel, Field
from app.engines.suppression_engine import SuppressionEngine, build_signature_from_timestamp


class SimilarIncidentsRequest(BaseModel):
    anomaly_signature: list[float] = Field(..., min_length=7, max_length=7)
    top_k: int = Field(default=5, ge=1, le=50)
    false_positives_only: bool = False


@router.post("/suppression/similar")
def retrieve_similar_historical_incidents(payload: SimilarIncidentsRequest, db: DBSession):
    """Retrieve Top-K nearest historical incidents via pgvector cosine distance (`<=>`)."""
    engine = get_suppression_engine(db)
    matches = engine.retrieve_similar_incidents(
        candidate_signature=payload.anomaly_signature,
        db=db,
        top_k=payload.top_k,
        false_positives_only=payload.false_positives_only,
    )
    return {
        "count": len(matches),
        "matches": matches,
    }


@router.post("/suppression/mark-false-positive/{incident_id}", response_model=MarkFalsePositiveResponse)
def mark_false_positive(incident_id: uuid.UUID, db: DBSession):
    """Mark an incident as a false positive (computing a cyclical 7D signature if missing) so future patterns are suppressed."""
    inc = db.scalar(select(Incident).where(Incident.id == incident_id))
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    inc.was_false_positive = True
    inc.learned_pattern_tag = inc.learned_pattern_tag or "user_labeled_false_positive"
    if inc.anomaly_signature is None:
        ts = inc.timestamp_start or datetime.now(timezone.utc)
        inc.anomaly_signature = build_signature_from_timestamp(
            timestamp=ts,
            service_id=str(inc.root_cause_service_id or "unknown-service"),
            metric_type=inc.root_cause_type or "latency_ms",
            severity_z=3.5,
        )
    db.commit()

    # Re-sync in-memory engine
    get_suppression_engine(db)

    return MarkFalsePositiveResponse(
        status="marked",
        incident_id=incident_id,
    )

