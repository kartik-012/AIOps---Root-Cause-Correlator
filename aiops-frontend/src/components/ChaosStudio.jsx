import React, { useState } from 'react'
import { sound } from '../utils/audio'

export function ChaosStudio({ onInject, onReset }) {
  const [loading, setLoading] = useState(false)

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

  const handleReset = async () => {
    sound.success()
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
    </div>
  )
}
