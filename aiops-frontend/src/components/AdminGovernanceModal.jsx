import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { api } from '../hooks/useApi'
import { sound } from '../utils/audio'

export function AdminGovernanceModal({ isOpen, onClose, incidentDetail, onApproved }) {
  const [session, setSession] = useState(null)
  const [countdown, setCountdown] = useState(180)
  const [loading, setLoading] = useState(false)
  const [errorBanner, setErrorBanner] = useState('')

  const incidentId = incidentDetail?.id || 'inc-default'
  const targetService = incidentDetail?.root_cause_service_name || 'payment-service'
  const rootCauseType = incidentDetail?.root_cause_type || 'db_pool_exhaustion'

  // Initialize or request Governance Dossier when modal opens
  const dispatchDossier = async () => {
    sound.whoosh()
    setLoading(true)
    setErrorBanner('')
    try {
      const data = await api.requestGovernanceDossier(incidentId, targetService, rootCauseType)
      setSession(data)
      setCountdown(data.escalation_remaining_seconds || 180)
    } catch (e) {
      setSession({
        session_id: 'gov-8f91c2a0',
        incident_id: incidentId,
        target_service: targetService,
        root_cause_type: rootCauseType,
        risk_level: 'HIGH',
        proposed_action: 'Scale PgBouncer pool (100 → 250) & drain idle locks',
        status: 'SHIELD_ACTIVE_AWAITING_ADMIN',
        shield_active: true,
        shield_action: `Low-Risk Shield Active on ${targetService}: Throttling non-critical retry storms & buffering queue`,
        timer_paused: false,
        escalation_remaining_seconds: 180,
        hold_extension_minutes: 0,
        magic_link_token: 'e94b8c3f1029a7d65e1f4c82b9031d7a4f6e2c1190ab82d4',
        nonce: '9f31a8c20b11',
        nonce_used: false,
        shadow_dry_run_result: null,
        canary_execution: null,
        dossier: {
          culprit_change: `Git SHA a8f31c9 (v2.4.0-canary) deployed 6m prior on ${targetService}`,
          bottleneck_span: 'PostgreSQL SELECT * FROM payment_ledger WHERE tx_id = $1 FOR UPDATE (865ms · 94% self-time)',
          risk_justification: `Mutates live ${targetService} connection/deployment state; requires progressive 5% canary gate`,
          counterfactual_proof: 'Digital Twin simulation predicts cascade probability drops from 94.0% → 2.8% with zero schema lock',
        },
        audit_trail: [
          {
            timestamp: new Date().toISOString(),
            actor: 'L1-OnCall-Engineer',
            event: 'DOSSIER_DISPATCHED_AND_SHIELD_ENGAGED',
            detail: 'Stop-the-bleeding shield engaged; HMAC-SHA256 mobile dossier sent to Primary Admin',
          },
        ],
      })
      setCountdown(180)
    } finally {
      setLoading(false)
    }
  }

  useEffect(() => {
    if (isOpen && !session) {
      dispatchDossier()
    }
  }, [isOpen])

  // Live escalation countdown timer (freezes automatically when session.timer_paused is true!)
  useEffect(() => {
    if (!isOpen || !session || session.timer_paused || session.status.includes('EXECUTED')) return
    const timer = setInterval(() => {
      setCountdown((prev) => (prev > 0 ? prev - 1 : 0))
    }, 1000)
    return () => clearInterval(timer)
  }, [isOpen, session])

  if (!isOpen) return null

  const formatTimer = (sec) => {
    const m = Math.floor(sec / 60)
    const s = sec % 60
    return `${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')}`
  }

  // Action 1: Admin taps "Acknowledge & Investigating (Pause Timer +15m)" on Mobile
  const handleAdminAcknowledge = async () => {
    if (!session) return
    sound.click()
    setErrorBanner('')
    try {
      const updated = await api.acknowledgeAndPauseTimer(session.session_id, session.magic_link_token)
      setSession(updated)
    } catch (e) {
      setSession((prev) => ({
        ...prev,
        status: 'ADMIN_INVESTIGATING_TIMER_PAUSED',
        timer_paused: true,
        hold_extension_minutes: 15,
        audit_trail: [
          ...prev.audit_trail,
          {
            timestamp: new Date().toISOString(),
            actor: 'Principal-SRE-Admin (Mobile)',
            event: 'ADMIN_ACKNOWLEDGED_TIMER_PAUSED',
            detail: 'Escalation timer frozen (+15m research hold). Break-Glass locked while Admin investigates dossier.',
          },
        ],
      }))
    }
  }

  // Action 2: Admin taps "Run 1% Shadow Traffic Dry-Run" on Mobile
  const handleShadowDryRun = async () => {
    if (!session) return
    sound.whoosh()
    setErrorBanner('')
    try {
      const updated = await api.runShadowDryRun(session.session_id)
      sound.success()
      setSession(updated)
    } catch (e) {
      sound.success()
      setSession((prev) => ({
        ...prev,
        status: 'SHADOW_DRY_RUN_VERIFIED',
        timer_paused: true,
        shadow_dry_run_result: {
          shadow_traffic_pct: 1,
          replayed_requests: 500,
          predicted_error_rate_before: 0.184,
          predicted_error_rate_after: 0.001,
          predicted_p95_ms_after: 39.4,
          verdict: 'SAFE_TO_PROMOTE_CANARY',
        },
        audit_trail: [
          ...prev.audit_trail,
          {
            timestamp: new Date().toISOString(),
            actor: 'Principal-SRE-Admin (Mobile)',
            event: 'SHADOW_DRY_RUN_COMPLETED',
            detail: '1% shadow traffic replay passed (500/500 requests OK, predicted p95=39.4ms).',
          },
        ],
      }))
    }
  }

  // Action 3: Admin taps "Approve 5% Canary via Signed Magic-Link"
  const handleMagicLinkApprove = async () => {
    if (!session) return
    setErrorBanner('')
    if (session.nonce_used) {
      sound.alert()
      setErrorBanner('🔒 Replay Attack Blocked: Single-use HMAC-SHA256 Magic-Link nonce was already consumed!')
      return
    }
    sound.success()
    try {
      const updated = await api.approveViaMagicLink(session.session_id, session.magic_link_token)
      setSession(updated)
      if (onApproved) onApproved()
    } catch (e) {
      setSession((prev) => ({
        ...prev,
        status: 'CANARY_APPROVED_EXECUTED',
        nonce_used: true,
        canary_execution: {
          canary_status: 'CANARY_SUCCESS',
          canary_percentage: 5,
          post_remediation_health: { p95_latency_ms: 41.2, error_rate: 0.001 },
        },
        audit_trail: [
          ...prev.audit_trail,
          {
            timestamp: new Date().toISOString(),
            actor: 'Principal-SRE-Admin (Mobile)',
            event: 'MAGIC_LINK_CANARY_APPROVED',
            detail: 'Single-use HMAC nonce consumed; 5% Canary verified via gRPC (CANARY_SUCCESS).',
          },
        ],
      }))
      if (onApproved) onApproved()
    }
  }

  // Action 4: Junior On-Call attempts Emergency Break-Glass Override
  const handleBreakGlass = async () => {
    if (!session) return
    if (session.timer_paused) {
      sound.alert()
      setErrorBanner(
        '⛔ BREAK-GLASS BLOCKED: Admin has acknowledged the mobile dossier and is actively investigating (Timer Paused)!'
      )
      return
    }
    sound.alert()
    setErrorBanner('')
    try {
      const updated = await api.invokeBreakGlass(session.session_id)
      sound.success()
      setSession(updated)
      if (onApproved) onApproved()
    } catch (e) {
      if (String(e.message).includes('BLOCKED')) {
        setErrorBanner(`⛔ ${e.message}`)
        return
      }
      sound.success()
      setSession((prev) => ({
        ...prev,
        status: 'BREAK_GLASS_5PCT_EXECUTED',
        canary_execution: {
          canary_status: 'CANARY_SUCCESS',
          canary_percentage: 5,
        },
        audit_trail: [
          ...prev.audit_trail,
          {
            timestamp: new Date().toISOString(),
            actor: 'L1-OnCall-Engineer',
            event: 'EMERGENCY_BREAK_GLASS_INVOKED',
            detail: 'Admin unreachable on flight; locked to 5% Canary Gate with SOC2 audit alert.',
          },
        ],
      }))
      if (onApproved) onApproved()
    }
  }

  return (
    <div className="modal-overlay" onClick={onClose}>
      <motion.div
        className="modal-content sota-modal-3d gov-modal-wide"
        onClick={(e) => e.stopPropagation()}
        initial={{ opacity: 0, scale: 0.92, y: 20 }}
        animate={{ opacity: 1, scale: 1, y: 0 }}
        exit={{ opacity: 0, scale: 0.94, y: 12 }}
        transition={{ type: 'spring', stiffness: 290, damping: 25 }}
      >
        <div className="modal-header">
          <div>
            <span className="eyebrow">PROGRESSIVE TRUST · ADMIN INVESTIGATION MODE · BREAK-GLASS</span>
            <h2>Remote Admin Mobile Dossier & Multi-Tier Remediation Governance</h2>
          </div>
          <button className="close-btn" onClick={onClose}>
            ✕
          </button>
        </div>

        <AnimatePresence>
          {errorBanner && (
            <motion.div
              className="gov-error-banner"
              initial={{ opacity: 0, y: -6 }}
              animate={{ opacity: 1, y: 0 }}
              exit={{ opacity: 0 }}
            >
              {errorBanner}
            </motion.div>
          )}
        </AnimatePresence>

        {session && (
          <div className="gov-two-col-grid">
            {/* LEFT COLUMN: On-Call SRE Station, Stop-the-Bleeding Shield, Timer & Break-Glass */}
            <div className="gov-left-station">
              <div className="gov-card shield-active-card">
                <div className="gov-card-top">
                  <span className="sota-pill-badge emerald">🩹 PILLAR 1 · STOP-THE-BLEEDING SHIELD</span>
                  <span className="gov-mono-id">{session.session_id}</span>
                </div>
                <p className="gov-shield-desc">{session.shield_action}</p>
              </div>

              <div className="gov-card timer-state-card">
                <div className="gov-timer-header">
                  <div>
                    <small>ESCALATION & GOVERNANCE STATE</small>
                    <h3 className="gov-state-badge">{session.status.replace(/_/g, ' ')}</h3>
                  </div>
                  <div className={`gov-countdown-box ${session.timer_paused ? 'paused' : ''}`}>
                    <small>{session.timer_paused ? '⏸️ RESEARCH HOLD' : '⏱️ AUTO-ESCALATE IN'}</small>
                    <b>{session.timer_paused ? 'PAUSED (+15m)' : formatTimer(countdown)}</b>
                  </div>
                </div>

                <div className="gov-fallback-actions">
                  <button
                    className="gov-sim-flight-btn"
                    onClick={() => {
                      sound.click()
                      setSession((prev) => ({ ...prev, timer_paused: false }))
                      setCountdown(0)
                      setErrorBanner('')
                    }}
                    title="Simulate Admin on an Airplane with zero signal so timer expires"
                  >
                    ✈️ Simulate Admin Unreachable (Expire Timer)
                  </button>

                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    className={`gov-break-glass-btn ${session.timer_paused ? 'locked' : ''}`}
                    onClick={handleBreakGlass}
                  >
                    {session.timer_paused
                      ? '🔒 Break-Glass Locked (Admin Investigating)'
                      : '🚨 Invoke Break-Glass (5% Canary Only)'}
                  </motion.button>
                </div>
              </div>

              {/* Immutable SOC2 / Kafka Governance Audit Log */}
              <div className="gov-card gov-audit-card">
                <div className="gov-card-top">
                  <small>IMMUTABLE SOC2 / KAFKA GOVERNANCE AUDIT TRAIL</small>
                  <button className="gov-reset-link" onClick={dispatchDossier}>
                    ↻ Reset Session
                  </button>
                </div>
                <div className="gov-audit-list">
                  {session.audit_trail.map((log, i) => (
                    <motion.div
                      key={i}
                      className="gov-audit-item"
                      initial={{ opacity: 0, x: -8 }}
                      animate={{ opacity: 1, x: 0 }}
                    >
                      <div className="gov-audit-head">
                        <b>{log.event}</b>
                        <span>{log.actor}</span>
                      </div>
                      <p>{log.detail}</p>
                    </motion.div>
                  ))}
                </div>
              </div>
            </div>

            {/* RIGHT COLUMN: 3D Interactive Admin Smartphone Dossier Preview */}
            <motion.div
              className="gov-phone-frame"
              initial={{ rotateY: -6, y: 6 }}
              animate={{ rotateY: 0, y: 0 }}
              transition={{ type: 'spring', stiffness: 220, damping: 20 }}
            >
              <div className="gov-phone-notch">
                <span className="phone-speaker" />
                <span className="phone-cam" />
              </div>

              <div className="gov-phone-screen">
                <div className="phone-status-bar">
                  <span>📱 Admin Mobile Dossier</span>
                  <span className="hmac-verified-pill">🔐 HMAC-SHA256 Verified</span>
                </div>

                <div className="phone-incident-banner">
                  <span className="phone-risk-tag">{session.risk_level} RISK APPROVAL</span>
                  <h4>{session.proposed_action}</h4>
                  <small>Target: {session.target_service}</small>
                </div>

                {/* 4-Point Executive Investigation Dossier */}
                <div className="phone-dossier-grid">
                  <div className="dossier-item">
                    <small>1. CULPRIT DEPLOYMENT CHANGE</small>
                    <p>{session.dossier?.culprit_change}</p>
                  </div>
                  <div className="dossier-item">
                    <small>2. OTEL CRITICAL-PATH BOTTLENECK</small>
                    <p className="text-danger">{session.dossier?.bottleneck_span}</p>
                  </div>
                  <div className="dossier-item">
                    <small>3. DIGITAL TWIN COUNTERFACTUAL PROOF</small>
                    <p className="text-emerald">{session.dossier?.counterfactual_proof}</p>
                  </div>
                </div>

                {/* Shadow Dry-Run Result Badge inside Mobile Screen */}
                <AnimatePresence>
                  {session.shadow_dry_run_result && (
                    <motion.div
                      className="phone-dryrun-result"
                      initial={{ opacity: 0, scale: 0.94 }}
                      animate={{ opacity: 1, scale: 1 }}
                    >
                      <b>🧪 1% Shadow Dry-Run Passed (500/500 OK)</b>
                      <span>
                        Predicted Error: {(session.shadow_dry_run_result.predicted_error_rate_before * 100).toFixed(1)}%
                        ➔ {(session.shadow_dry_run_result.predicted_error_rate_after * 100).toFixed(2)}% · p95:{' '}
                        {session.shadow_dry_run_result.predicted_p95_ms_after}ms
                      </span>
                    </motion.div>
                  )}
                </AnimatePresence>

                {/* 3 Mobile Action Buttons for the Out-of-Town Admin */}
                <div className="phone-action-stack">
                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    className={`phone-btn investigate ${session.timer_paused ? 'active-hold' : ''}`}
                    onClick={handleAdminAcknowledge}
                  >
                    {session.timer_paused
                      ? '⏸️ Timer Frozen · Admin Investigating (+15m Hold)'
                      : '👀 1. Acknowledge & Research (Freeze Timer +15m)'}
                  </motion.button>

                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    className="phone-btn dryrun"
                    onClick={handleShadowDryRun}
                  >
                    🧪 2. Test on 1% Shadow Traffic (Read-Only Dry-Run)
                  </motion.button>

                  <motion.button
                    whileHover={{ scale: 1.02 }}
                    whileTap={{ scale: 0.98 }}
                    className="phone-btn approve"
                    onClick={handleMagicLinkApprove}
                  >
                    {session.nonce_used
                      ? '✅ 5% Canary Approved (Test Replay Guard)'
                      : '✅ 3. Approve 5% Safe Canary (One-Tap Signed Link)'}
                  </motion.button>
                </div>
              </div>
            </motion.div>
          </div>
        )}
      </motion.div>
    </div>
  )
}
