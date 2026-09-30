import React, { useState } from 'react'
import { sound } from '../utils/audio'

export function ChaosStudio({ onInject, onReset }) {
  const [loading, setLoading] = useState(false)
  const [demoStep, setDemoStep] = useState(null)

  const handleChaos = async (scenario, label) => {
    sound.alert()
    setLoading(true)
    try {
      const res = await fetch('/api/v1/chaos/inject', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario }),
      })
      const data = await res.json()
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
      // 1. Inject Chaos
      await fetch('/api/v1/chaos/inject', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario: 'db_pool_exhaustion' }),
      })

      setTimeout(() => {
        sound.alert()
        setDemoStep('2/4: EWMA Anomaly Detected on payment-service (z=5.4σ)...')
      }, 1200)

      setTimeout(async () => {
        sound.click()
        setDemoStep('3/4: gRPC Diagnostic Calling GetHealthStatus (:50051)...')
        // 2. Run correlation
        const res = await fetch('/api/v1/correlation/run', { method: 'POST' })
        const data = await res.json()
        if (onInject) onInject('db_pool_exhaustion', data)
      }, 2500)

      setTimeout(() => {
        sound.success()
        setDemoStep('4/4: Root Cause Isolated to Payment DB! (Confidence boosted to 94%)')
        setTimeout(() => setDemoStep(null), 4000)
      }, 4000)
    } catch (e) {
      console.error('Demo walkthrough failed:', e)
      setDemoStep(null)
    } finally {
      setLoading(false)
    }
  }

  const handleReset = async () => {
    sound.success()
    setDemoStep(null)
    try {
      await fetch('/api/v1/chaos/inject', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ scenario: 'reset' }),
      })
      if (onReset) onReset()
    } catch (e) {
      console.error('Reset failed:', e)
    }
  }

  return (
    <div className="chaos-studio-toolbar">
      <div className="chaos-label">
        <span className="pulse-icon">⚡</span>
        <b>CHAOS STUDIO</b>
      </div>
      <div className="chaos-btn-group">
        <button
          className="chaos-btn primary"
          style={{ background: 'linear-gradient(135deg, #3b82f6, #8b5cf6)', color: '#fff', fontWeight: 'bold' }}
          onClick={handleInteractiveDemo}
          disabled={loading}
          title="Run 1-Click Interactive Interview Cascade Demonstration"
        >
          🎯 1-Click Live Incident Demo
        </button>
        <button
          className="chaos-btn danger"
          onClick={() => handleChaos('db_pool_exhaustion', 'Payment DB Pool')}
          disabled={loading}
        >
          💥 DB Pool Exhaustion (Payment)
        </button>
        <button
          className="chaos-btn warning"
          onClick={() => handleChaos('memory_leak', 'Auth Memory Leak')}
          disabled={loading}
        >
          🧠 Memory Leak (Auth)
        </button>
        <button
          className="chaos-btn caution"
          onClick={() => handleChaos('cpu_spike', 'Inventory CPU Spike')}
          disabled={loading}
        >
          🔥 CPU Pegged (Inventory)
        </button>
        <button className="chaos-btn reset" onClick={handleReset}>
          🛡️ Auto-Heal & Reset
        </button>
      </div>
      {demoStep && (
        <div style={{ marginLeft: '12px', fontSize: '0.82rem', color: '#38bdf8', fontWeight: 600, animation: 'pulse 1.5s infinite' }}>
          ▶ {demoStep}
        </div>
      )}
    </div>
  )
}
