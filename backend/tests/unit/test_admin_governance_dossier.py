"""Unit tests for Progressive Trust, Admin Investigation Mode, HMAC-SHA256 Mobile Dossier, and Break-Glass Governance."""

import pytest
from app.engines.remediation_engine import RemediationEngine
from app.grpc_services.service_states import ServiceStateManager


@pytest.mark.asyncio
async def test_admin_investigation_mode_pause_timer_shadow_dry_run_and_magic_link_approval():
    """Verify:
    1. Creating a governance dossier immediately engages the Stop-the-Bleeding shield.
    2. Admin tapping 'Acknowledge & Investigating' freezes the timer and blocks Junior Break-Glass.
    3. Admin running 1% Shadow Dry-Run verifies safety without touching production.
    4. Admin tapping Approve via HMAC-SHA256 Magic-Link executes 5% Canary and blocks replay attacks.
    """
    state_mgr = ServiceStateManager()
    state_mgr.inject_fault("payment-service", "db_pool_exhaustion")
    engine = RemediationEngine(state_manager=state_mgr)

    # 1. Junior SRE dispatches Mobile Dossier to Admin
    session = engine.create_governance_dossier(
        incident_id="inc-gov-101",
        target_service="payment-service",
        root_cause_type="db_pool_exhaustion",
        requester="junior-sre-alex",
    )
    session_id = session["session_id"]
    token = session["magic_link_token"]

    assert session["shield_active"] is True
    assert session["status"] == "SHIELD_ACTIVE_AWAITING_ADMIN"
    assert session["timer_paused"] is False
    assert "PostgreSQL SELECT" in session["dossier"]["bottleneck_span"]

    # 2. Admin opens Mobile Dossier and taps 'Acknowledge & Research (+15m Hold)'
    ack_session = engine.acknowledge_and_hold_timer(
        session_id=session_id,
        token=token,
        admin_actor="Admin-Sarah (Mobile)",
        hold_minutes=15,
    )
    assert ack_session["timer_paused"] is True
    assert ack_session["status"] == "ADMIN_INVESTIGATING_TIMER_PAUSED"

    # Verify Junior Break-Glass is strictly BLOCKED while Admin is actively investigating!
    with pytest.raises(ValueError, match="Break-Glass Override BLOCKED"):
        await engine.execute_break_glass_override(session_id, junior_actor="impatient-junior")

    # 3. Admin runs 1% Shadow Traffic Dry-Run from mobile
    dry_session = engine.run_shadow_dry_run(session_id=session_id, admin_actor="Admin-Sarah (Mobile)")
    assert dry_session["shadow_dry_run_result"]["verdict"] == "SAFE_TO_PROMOTE_CANARY"
    assert dry_session["status"] == "SHADOW_DRY_RUN_VERIFIED"

    # 4. Admin taps 'Approve 5% Canary' via signed Magic-Link
    approved_session = await engine.approve_via_magic_link(
        session_id=session_id,
        token=token,
        admin_actor="Admin-Sarah (Mobile)",
    )
    assert approved_session["status"] == "CANARY_APPROVED_EXECUTED"
    assert approved_session["nonce_used"] is True
    assert approved_session["canary_execution"]["canary_status"] == "CANARY_SUCCESS"

    # 5. Replay attack check: clicking the same magic-link a second time MUST fail
    with pytest.raises(ValueError, match="Replay Attack Blocked"):
        await engine.approve_via_magic_link(session_id=session_id, token=token)


@pytest.mark.asyncio
async def test_unreachable_admin_airplane_fallback_allows_5pct_canary_break_glass():
    """Verify that if the Admin never acknowledges (e.g., on a flight, timer_paused=False),
    Break-Glass override is permitted and constrained to a 5% Canary rollout.
    """
    state_mgr = ServiceStateManager()
    state_mgr.inject_fault("payment-service", "db_pool_exhaustion")
    engine = RemediationEngine(state_manager=state_mgr)

    session = engine.create_governance_dossier(
        incident_id="inc-gov-flight-202",
        target_service="payment-service",
        root_cause_type="db_pool_exhaustion",
        requester="junior-sre-alex",
    )
    assert session["timer_paused"] is False

    bg_session = await engine.execute_break_glass_override(
        session_id=session["session_id"],
        junior_actor="junior-sre-alex",
        justification="Admin on flight; checkout outage > $5k/min",
    )
    assert bg_session["status"] == "BREAK_GLASS_5PCT_EXECUTED"
    assert bg_session["canary_execution"]["canary_percentage"] == 5
    assert bg_session["canary_execution"]["canary_status"] == "CANARY_SUCCESS"
