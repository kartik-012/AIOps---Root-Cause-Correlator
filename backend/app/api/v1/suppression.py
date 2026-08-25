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
    """Check a 7-dim anomaly signature against known false positives and log if matched."""
    engine = get_suppression_engine(db)
    decision = engine.evaluate(payload.anomaly_signature)

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


@router.post("/suppression/mark-false-positive/{incident_id}", response_model=MarkFalsePositiveResponse)
def mark_false_positive(incident_id: uuid.UUID, db: DBSession):
    """Mark an incident as a false positive so future matching patterns are suppressed."""
    inc = db.scalar(select(Incident).where(Incident.id == incident_id))
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    inc.was_false_positive = True
    inc.learned_pattern_tag = inc.learned_pattern_tag or "user_labeled_false_positive"
    db.commit()

    # Re-sync in-memory engine
    get_suppression_engine(db)

    return MarkFalsePositiveResponse(
        status="marked",
        incident_id=incident_id,
    )
