import React, { useState } from 'react'
import { Panel } from './Panel'
import { api } from '../hooks/useApi'

export function EvaluationModal({ isOpen, onClose }) {
  const [metrics, setMetrics] = useState(null)
  const [loading, setLoading] = useState(false)

  const runBenchmark = async () => {
    setLoading(true)
    try {
      const data = await api.runEvaluationScenarios()
      setMetrics(data)
    } catch (e) {
      console.error('Benchmark evaluation failed:', e)
    } finally {
      setLoading(false)
    }
  }

  if (!isOpen) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <span className="eyebrow">GROUND-TRUTH BENCHMARK</span>
            <h2>Synthetic Scenario Evaluation (30 Scenarios)</h2>
          </div>
          <button className="close-btn" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="modal-body">
          <p className="modal-desc">
            Executes all 30 ground-truth injected failure scenarios (single root cause, multi-root cause,
            converging cascades, and false positive patterns) against the real Python engines.
          </p>

          <button className="run-bench-btn" onClick={runBenchmark} disabled={loading}>
            {loading ? 'Executing 30 Scenarios...' : 'Run Full Benchmark Suite 🚀'}
          </button>

          {metrics && (
            <div className="benchmark-grid">
              <div className="metric-card">
                <small>TOP-1 ACCURACY</small>
                <b>{(metrics.top1_accuracy * 100).toFixed(1)}%</b>
              </div>
              <div className="metric-card">
                <small>TOP-3 ACCURACY</small>
                <b>{(metrics.top3_accuracy * 100).toFixed(1)}%</b>
              </div>
              <div className="metric-card">
                <small>MULTI-ROOT SEPARATION</small>
                <b>{(metrics.multi_incident_separation_accuracy * 100).toFixed(1)}%</b>
              </div>
              <div className="metric-card">
                <small>SUPPRESSION PRECISION</small>
                <b>{(metrics.suppression_precision * 100).toFixed(1)}%</b>
              </div>
              <div className="metric-card">
                <small>SUPPRESSION RECALL</small>
                <b>{(metrics.suppression_recall * 100).toFixed(1)}%</b>
              </div>
              <div className="metric-card">
                <small>BLAST RADIUS ACCURACY</small>
                <b>{(metrics.blast_radius_accuracy * 100).toFixed(1)}%</b>
              </div>
              <div className="metric-card full-width">
                <small>BENCHMARK RESULT</small>
                <b>
                  {metrics.passed} / {metrics.total_scenarios} Scenarios Passed · Avg Detection Time{' '}
                  {metrics.mean_detection_time_seconds}s
                </b>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
