"""Runbook suggestions router — Remediation library lookup and human-in-the-loop approval."""

import json
from pathlib import Path
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, HTTPException
from sqlalchemy import select

from app.dependencies import DBSession
from app.models.db_models import Incident, RunbookSuggestion
from app.models.schemas import RunbookResponse, RunbookApproveResponse

router = APIRouter()

RUNBOOK_FILE = Path(__file__).resolve().parent.parent.parent / "runbooks" / "runbook_library.json"


def _load_runbooks() -> dict:
    if RUNBOOK_FILE.exists():
        with open(RUNBOOK_FILE, "r") as fp:
            return json.load(fp)
    return {}


@router.get("/runbook/{root_cause_type}", response_model=RunbookResponse)
def get_runbook(root_cause_type: str):
    """Retrieve suggested remediation runbook for a root cause type."""
    library = _load_runbooks()
    entry = library.get(root_cause_type)
    if not entry:
        # Fallback default generic runbook
        return RunbookResponse(
            title=f"Incident Remediation: {root_cause_type.replace('_', ' ').title()}",
            severity="medium",
            suggested_action=f"Investigate anomalous telemetry on affected service, inspect container logs, and verify recent configuration deployments.",
            steps=[
                "Check pod status and restart count",
                "Inspect recent application logs for unhandled exceptions",
                "Review recent deployments and roll back if necessary",
                "Verify upstream and downstream health metrics",
            ],
            prevention="Add SLO alerts and regression tests in deployment pipeline",
        )

    suggested = entry["steps"][0] if entry.get("steps") else ""
    return RunbookResponse(
        title=entry.get("title", root_cause_type),
        severity=entry.get("severity", "medium"),
        suggested_action=suggested,
        steps=entry.get("steps", []),
        prevention=entry.get("prevention"),
    )


@router.post("/runbook/{incident_id}/approve", response_model=RunbookApproveResponse)
def approve_runbook(incident_id: uuid.UUID, db: DBSession):
    """Human-in-the-loop approval of suggested runbook action before any remediation proceeds."""
    inc = db.scalar(select(Incident).where(Incident.id == incident_id))
    if not inc:
        raise HTTPException(status_code=404, detail="Incident not found")

    # Record approval
    suggestion = db.scalar(
        select(RunbookSuggestion)
        .where(RunbookSuggestion.incident_id == incident_id)
        .order_by(RunbookSuggestion.suggested_at.desc())
    )

    if suggestion:
        suggestion.was_approved = True
    else:
        # Create suggestion entry if not present
        r_type = inc.root_cause_type or "unknown"
        rb = get_runbook(r_type)
        suggestion = RunbookSuggestion(
            incident_id=incident_id,
            root_cause_type=r_type,
            suggested_action=rb.suggested_action or "Remediation verified",
            was_approved=True,
            suggested_at=datetime.now(timezone.utc),
        )
        db.add(suggestion)

    db.commit()

    return RunbookApproveResponse(
        status="approved",
        incident_id=incident_id,
    )
