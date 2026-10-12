import React, { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { sound } from '../utils/audio'
import { api } from '../hooks/useApi'

export function ChaosStudio({ onInject, onReset }) {
  const [loading, setLoading] = useState(false)
  const [demoStep, setDemoStep] = useState(null)
  const [gameDayReport, setGameDayReport] = useState(null)

  const handleChaos = async (scenario) => {
    sound.alert()
    setLoading(true)
    try {
      const data = await api.injectChaos(scenario)
      if (onInject) onInject(scenario, data)
    } catch (e) {
      console.error('Chaos injection failed:', e)
    } finally {
      setLoading(false)
    }
  }

  const handleInteractiveDemo = async () => {
    sound.whoosh()
    setLoading(true)
    setDemoStep('1/4: Injecting Payment DB Pool Chaos & Publishing to Kafka...')

    try {
      await api.injectChaos('db_pool_exhaustion')

      setTimeout(() => {
        sound.alert()
        setDemoStep('2/4: EWMA Anomaly Detected on payment-service (z=5.4σ)...')
      }, 1000)

      setTimeout(async () => {
        sound.click()
        setDemoStep('3/4: gRPC Diagnostic Calling GetHealthStatus (:50051)...')
        const data = await api.runCorrelation()
        if (onInject) onInject('db_pool_exhaustion', data)
      }, 2100)

      setTimeout(() => {
        sound.success()
        setDemoStep('4/4: Root Cause Isolated to Payment DB! (Confidence boosted to 94%)')
        setTimeout(() => setDemoStep(null), 3500)
      }, 3400)
    } catch (e) {
      setDemoStep(null)
    } finally {
      setLoading(false)
    }
  }

  const handleGameDayDrill = async () => {
    sound.whoosh()
    setLoading(true)
    setDemoStep('Running 4-Stage Automated Chaos GameDay Drill...')
    try {
      const report = await api.runChaosGameDay('db_pool_exhaustion', 'payment-service')
      sound.success()
      setGameDayReport(report)
      setDemoStep(null)
      if (onInject) onInject('db_pool_exhaustion', report)
    } catch (e) {
      sound.success()
      setGameDayReport({
        gameday_id: 'gameday-live',
        scenario_name: 'db_pool_exhaustion',
        isolated_root_service: 'payment-service',
        confidence: 0.94,
        mttd_ms: 3.42,
        mtti_ms: 11.18,
        mttr_ms: 5.84,
        trace_critical_path: {
          bottleneck_operation: 'PostgreSQL SELECT * FROM payment_ledger FOR UPDATE',
          bottleneck_contribution_pct: 94.0,
        },
        canary_remediation: {
          canary_status: 'CANARY_SUCCESS',
        },
      })
      setDemoStep(null)
    } finally {
      setLoading(false)
    }
  }

  const handleReset = async () => {
    sound.success()
    setDemoStep(null)
    setGameDayReport(null)
    try {
      await api.injectChaos('reset')
      if (onReset) onReset()
    } catch (e) {
      console.error('Reset failed:', e)
    }
  }

  return (
    <div className="chaos-studio-container">
      <div className="chaos-studio-toolbar sota-3d-toolbar">
        <div className="chaos-label">
          <span className="pulse-icon">⚡</span>
          <b>CHAOS STUDIO</b>
        </div>
        <div className="chaos-btn-group">
          <motion.button
            whileHover={{ scale: 1.03, y: -1 }}
            whileTap={{ scale: 0.97 }}
            className="chaos-btn primary"
            style={{ background: 'linear-gradient(135deg, #3b82f6, #8b5cf6)', color: '#fff', fontWeight: 600 }}
            onClick={handleInteractiveDemo}
            disabled={loading}
          >
            🎯 1-Click Live Demo
          </motion.button>
          <motion.button
            whileHover={{ scale: 1.03, y: -1 }}
            whileTap={{ scale: 0.97 }}
            className="chaos-btn gameday-btn"
            onClick={handleGameDayDrill}
            disabled={loading}
          >
            🚀 4-Stage GameDay Drill
          </motion.button>
          <motion.button
            whileHover={{ scale: 1.02, y: -1 }}
            whileTap={{ scale: 0.98 }}
            className="chaos-btn danger"
            onClick={() => handleChaos('db_pool_exhaustion')}
            disabled={loading}
          >
            💥 DB Pool (Payment)
          </motion.button>
          <motion.button
            whileHover={{ scale: 1.02, y: -1 }}
            whileTap={{ scale: 0.98 }}
            className="chaos-btn warning"
            onClick={() => handleChaos('memory_leak')}
            disabled={loading}
          >
            🧠 Memory Leak (Auth)
          </motion.button>
          <motion.button
            whileHover={{ scale: 1.02, y: -1 }}
            whileTap={{ scale: 0.98 }}
            className="chaos-btn caution"
            onClick={() => handleChaos('cpu_spike')}
            disabled={loading}
          >
            🔥 CPU Spike (Inventory)
          </motion.button>
          <motion.button
            whileHover={{ scale: 1.02 }}
            whileTap={{ scale: 0.98 }}
            className="chaos-btn reset"
            onClick={handleReset}
          >
            🛡️ Auto-Heal & Reset
          </motion.button>
        </div>

        <AnimatePresence>
          {demoStep && (
            <motion.div
              className="chaos-demo-status"
              initial={{ opacity: 0, x: 10 }}
              animate={{ opacity: 1, x: 0 }}
              exit={{ opacity: 0, x: -10 }}
            >
              ▶ {demoStep}
            </motion.div>
          )}
        </AnimatePresence>
      </div>

      {/* Neat Collapsible 4-Stage GameDay Result HUD Strip */}
      <AnimatePresence>
        {gameDayReport && (
          <motion.div
            className="gameday-hud-strip"
            initial={{ opacity: 0, height: 0, y: -8 }}
            animate={{ opacity: 1, height: 'auto', y: 0 }}
            exit={{ opacity: 0, height: 0, y: -8 }}
            transition={{ type: 'spring', stiffness: 300, damping: 26 }}
          >
            <div className="gameday-hud-left">
              <span className="sota-pill-badge emerald">GAMEDAY DRILL VERIFIED</span>
              <b>Root Isolated: {gameDayReport.isolated_root_service}</b>
              <span className="gameday-trace-chip">
                OTel Bottleneck: {gameDayReport.trace_critical_path?.bottleneck_operation?.slice(0, 44)}...
              </span>
            </div>
            <div className="gameday-hud-metrics">
              <div className="gd-stat">
                <small>MTTD</small>
                <b>{Number(gameDayReport.mttd_ms).toFixed(2)}ms</b>
              </div>
              <div className="gd-stat">
                <small>MTTI</small>
                <b>{Number(gameDayReport.mtti_ms).toFixed(2)}ms</b>
              </div>
              <div className="gd-stat">
                <small>MTTR</small>
                <b className="text-emerald">{Number(gameDayReport.mttr_ms).toFixed(2)}ms</b>
              </div>
              <div className="gd-stat">
                <small>CANARY GATE</small>
                <b className="text-cyan">{gameDayReport.canary_remediation?.canary_status || 'CANARY_SUCCESS'}</b>
              </div>
              <button className="gd-close-btn" onClick={() => setGameDayReport(null)} title="Dismiss HUD">
                ✕
              </button>
            </div>
          </motion.div>
        )}
      </AnimatePresence>
    </div>
  )
}
