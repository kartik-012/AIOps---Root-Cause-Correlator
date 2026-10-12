"""Runbook suggestions router — Remediation library lookup and human-in-the-loop approval."""

import json
from pathlib import Path
import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select

from app.dependencies import DBSession
from app.security import verify_operator_access
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
            suggested_action="Investigate anomalous telemetry on affected service, inspect container logs, and verify recent configuration deployments.",
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
async def approve_runbook(
    incident_id: uuid.UUID,
    db: DBSession,
    _operator: str = Depends(verify_operator_access),
):
    """Human-in-the-loop approval of suggested runbook action with closed-loop health restoration & Kafka audit log."""
    from fastapi.concurrency import run_in_threadpool
    from app.models.db_models import Service
    from app.grpc_services.diagnostic_server import _global_state_manager
    from app.kafka import get_kafka_producer
    from app.kafka.events import AuditEvent, RemediationEvent

    def _approve_sync():
        inc = db.scalar(select(Incident).where(Incident.id == incident_id))
        if not inc:
            return None

        now = datetime.now(timezone.utc)
        r_type = inc.root_cause_type or "unknown"
        rb = get_runbook(r_type)
        action_text = rb.suggested_action or "Remediation verified"

        # Record approval on RunbookSuggestion
        suggestion = db.scalar(
            select(RunbookSuggestion)
            .where(RunbookSuggestion.incident_id == incident_id)
            .order_by(RunbookSuggestion.suggested_at.desc())
        )

        if suggestion:
            suggestion.was_approved = True
            action_text = suggestion.suggested_action or action_text
        else:
            suggestion = RunbookSuggestion(
                incident_id=incident_id,
                root_cause_type=r_type,
                suggested_action=action_text,
                was_approved=True,
                suggested_at=now,
            )
            db.add(suggestion)

        inc.resolution_action = action_text
        if inc.timestamp_end is None:
            inc.timestamp_end = now

        # Differentiator #9: Closed-loop health restoration on ServiceStateManager
        target_svc_name = "unknown-service"
        if inc.root_cause_service_id:
            svc = db.scalar(select(Service).where(Service.id == inc.root_cause_service_id))
            if svc and svc.name:
                target_svc_name = svc.name
                _global_state_manager.restore_health(svc.name)

        db.commit()
        return {
            "incident_id": str(incident_id),
            "root_cause_type": r_type,
            "target_service": target_svc_name,
            "action_text": action_text,
            "approved_at": now.isoformat(),
        }

    audit_meta = await run_in_threadpool(_approve_sync)
    if audit_meta is None:
        raise HTTPException(status_code=404, detail="Incident not found")

    # Emit human-in-the-loop Kafka remediation & audit events (Step 8 FinTech audit compliance)
    producer = get_kafka_producer()
    try:
        await producer.publish_remediation(
            RemediationEvent(
                incident_id=audit_meta["incident_id"],
                action=audit_meta["action_text"],
                status="completed",
                approved_by=_operator or "sre-operator",
            )
        )
        await producer.publish_audit(
            AuditEvent(
                event_type="runbook_approved",
                actor=_operator or "sre-operator",
                details=audit_meta,
            )
        )
    except Exception:
        pass

    return RunbookApproveResponse(
        status="approved",
        incident_id=incident_id,
    )


@router.post("/runbook/{incident_id}/execute-canary")
async def execute_canary_remediation(
    incident_id: str,
    target_service: str = "payment-service",
    root_cause_type: str = "db_pool_exhaustion",
    canary_percent: int = 5,
    _operator: str = Depends(verify_operator_access),
):
    """Execute a remediation plan in Canary mode (e.g., 5% traffic slice) with automatic circuit-breaker rollback."""
    from app.engines.remediation_engine import get_remediation_engine

    rem_engine = get_remediation_engine()
    plan = rem_engine.generate_plan(
        incident_id=incident_id,
        root_cause_type=root_cause_type,
        target_service=target_service,
    )
    executed = await rem_engine.execute_canary_with_safety_circuit_breaker(
        plan_id=plan.plan_id,
        approver=_operator or "sre-operator",
        canary_percent=canary_percent,
        verify_health=True,
    )
    bandit_state = rem_engine.bandit.record_outcome(
        root_cause_type=root_cause_type,
        action_id=executed.action_title,
        resolved=(executed.canary_status == "CANARY_SUCCESS"),
    )
    return {
        "plan": executed.to_dict(),
        "bandit_posterior": bandit_state,
    }


@router.get("/runbook/{root_cause_type}/bandit-rankings")
def get_bandit_ranked_runbooks(root_cause_type: str):
    """Return candidate remediation runbooks ranked by online Beta-Bernoulli Thompson Sampling bandit."""
    from app.engines.remediation_engine import get_remediation_engine

    library = _load_runbooks()
    entry = library.get(root_cause_type, {})
    steps = entry.get("steps", ["Scale connection pool", "Rolling restart with heap dump", "Rollback canary deploy"])
    candidates = [{"action_id": f"step_{idx+1}", "title": s} for idx, s in enumerate(steps)]
    rem_engine = get_remediation_engine()
    ranked = rem_engine.bandit.rank_runbooks(root_cause_type, candidates, explore=False)
    return {
        "root_cause_type": root_cause_type,
        "ranked_actions": ranked,
    }


@router.post("/runbook/{incident_id}/governance/request-dossier")
def request_admin_governance_dossier(
    incident_id: str,
    target_service: str = "payment-service",
    root_cause_type: str = "db_pool_exhaustion",
    requester: str = "L1-OnCall-Engineer",
):
    """Stage a remediation with an immediate Low-Risk 'Stop-the-Bleeding' Shield and dispatch an HMAC-SHA256 Mobile Dossier."""
    from app.engines.remediation_engine import get_remediation_engine

    rem_engine = get_remediation_engine()
    return rem_engine.create_governance_dossier(
        incident_id=incident_id,
        target_service=target_service,
        root_cause_type=root_cause_type,
        requester=requester,
    )


@router.post("/runbook/governance/{session_id}/acknowledge-investigate")
def acknowledge_and_pause_escalation_timer(
    session_id: str,
    token: str,
    admin_actor: str = "Principal-SRE-Admin (Mobile)",
    hold_minutes: int = 15,
):
    """Admin taps 'Acknowledge & Investigating' on mobile: freezes escalation timer and locks Break-Glass."""
    from app.engines.remediation_engine import get_remediation_engine

    rem_engine = get_remediation_engine()
    try:
        return rem_engine.acknowledge_and_hold_timer(
            session_id=session_id,
            token=token,
            admin_actor=admin_actor,
            hold_minutes=hold_minutes,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/runbook/governance/{session_id}/shadow-dry-run")
def execute_shadow_traffic_dry_run(
    session_id: str,
    admin_actor: str = "Principal-SRE-Admin (Mobile)",
):
    """Execute a 1% read-only shadow traffic dry-run simulation for the Admin."""
    from app.engines.remediation_engine import get_remediation_engine

    rem_engine = get_remediation_engine()
    try:
        return rem_engine.run_shadow_dry_run(session_id=session_id, admin_actor=admin_actor)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))


@router.post("/runbook/governance/{session_id}/approve-magic-link")
async def approve_remediation_via_magic_link(
    session_id: str,
    token: str,
    admin_actor: str = "Principal-SRE-Admin (Mobile)",
):
    """Verify single-use HMAC-SHA256 Magic-Link token and execute 5% Canary rollout."""
    from app.engines.remediation_engine import get_remediation_engine

    rem_engine = get_remediation_engine()
    try:
        return await rem_engine.approve_via_magic_link(
            session_id=session_id,
            token=token,
            admin_actor=admin_actor,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/runbook/governance/{session_id}/break-glass")
async def invoke_emergency_break_glass(
    session_id: str,
    junior_actor: str = "L1-OnCall-Engineer",
    justification: str = "Primary Admin unreachable on flight; checkout revenue impact > $5k/min",
):
    """Invoke emergency 5% Canary Break-Glass override (blocked if Admin is actively investigating)."""
    from app.engines.remediation_engine import get_remediation_engine

    rem_engine = get_remediation_engine()
    try:
        return await rem_engine.execute_break_glass_override(
            session_id=session_id,
            junior_actor=junior_actor,
            justification=justification,
        )
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

