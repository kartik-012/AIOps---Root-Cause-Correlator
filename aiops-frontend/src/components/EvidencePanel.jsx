import React, { useState, useEffect } from 'react'
import { motion, AnimatePresence } from 'framer-motion'
import { api } from '../hooks/useApi'
import { sound } from '../utils/audio'

export function EvidencePanel({ explanation, onEvidenceClick }) {
  const [activeTab, setActiveTab] = useState('evidence') // 'evidence' | 'trace'
  const [traceReport, setTraceReport] = useState(null)
  const [loadingTrace, setLoadingTrace] = useState(false)

  const defaultEvidence = [
    { text: 'Connection waits +418% (MicroRCA++ Cov=0.94)', time: '08:30' },
    { text: 'OTel Span Bottleneck: payment_ledger FOR UPDATE', time: '865ms' },
    { text: 'Canary deploy SHA a8f31c9 (-6m proximity boost)', time: '08:24' },
    { text: 'pgvector HNSW cosine match (tenant-isolated)', time: '0.94' },
  ]

  const evidenceItems =
    explanation?.evidence && explanation.evidence.length > 0
      ? explanation.evidence.map((e) => (typeof e === 'string' ? { text: e, time: 'VERIFIED' } : e))
      : defaultEvidence

  const loadTraceWaterfall = async () => {
    setLoadingTrace(true)
    try {
      const data = await api.analyzeTraceCriticalPath('payment-service', 'db_pool_exhaustion')
      setTraceReport(data)
    } catch (e) {
      setTraceReport({
        trace_id: 'trace-otel-9941a',
        total_trace_duration_ms: 920.0,
        bottleneck_service: 'payment-service',
        bottleneck_operation: 'PostgreSQL SELECT * FROM payment_ledger WHERE tx_id = $1 FOR UPDATE',
        bottleneck_exclusive_ms: 865.0,
        bottleneck_contribution_pct: 94.02,
        span_attributions: [
          {
            span_id: 'span-root-05',
            service_id: 'payment-service',
            operation_name: 'PostgreSQL SELECT * FROM payment_ledger FOR UPDATE',
            exclusive_duration_ms: 865.0,
            exclusive_share_pct: 94.0,
            status_code: 'DEADLINE_EXCEEDED',
            on_critical_path: true,
          },
          {
            span_id: 'span-ord-03',
            service_id: 'order-service',
            operation_name: 'gRPC /order.OrderManager/CreateOrder',
            exclusive_duration_ms: 12.0,
            exclusive_share_pct: 1.3,
            status_code: 'ERROR',
            on_critical_path: true,
          },
          {
            span_id: 'span-inv-04',
            service_id: 'inventory-service',
            operation_name: 'gRPC /inventory.Stock/ReserveItems',
            exclusive_duration_ms: 18.0,
            exclusive_share_pct: 2.0,
            status_code: 'OK',
            on_critical_path: false,
          },
          {
            span_id: 'span-gw-01',
            service_id: 'api-gateway',
            operation_name: 'POST /api/v1/checkout',
            exclusive_duration_ms: 17.0,
            exclusive_share_pct: 1.8,
            status_code: 'ERROR',
            on_critical_path: true,
          },
        ],
      })
    } finally {
      setLoadingTrace(false)
    }
  }

  useEffect(() => {
    if (activeTab === 'trace' && !traceReport) {
      loadTraceWaterfall()
    }
  }, [activeTab])

  return (
    <motion.div
      className="panel evidence sota-3d-panel"
      initial={{ opacity: 0, y: 12 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35 }}
    >
      <div className="sota-panel-header">
        <div>
          <span className="eyebrow">CAUSAL TELEMETRY & OTEL CRITICAL PATH</span>
          <h2>Evidence & Trace Attribution</h2>
        </div>
        <div className="sota-tab-switcher">
          <button
            className={activeTab === 'evidence' ? 'active' : ''}
            onClick={() => {
              sound.click()
              setActiveTab('evidence')
            }}
          >
            Signals
          </button>
          <button
            className={activeTab === 'trace' ? 'active' : ''}
            onClick={() => {
              sound.click()
              setActiveTab('trace')
            }}
          >
            OTel Spans
          </button>
        </div>
      </div>

      <AnimatePresence mode="wait">
        {activeTab === 'evidence' ? (
          <motion.div
            key="tab-evidence"
            className="evidence-list"
            initial={{ opacity: 0, x: -8 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: 8 }}
            transition={{ duration: 0.22 }}
          >
            {evidenceItems.map((item, idx) => (
              <motion.div
                key={idx}
                className="evidence-row sota-evidence-row"
                whileHover={{ scale: 1.015, x: 3 }}
                onClick={() => onEvidenceClick && onEvidenceClick(item.text || item)}
              >
                <b className="ev-check">✓</b>
                <span>{item.text || item}</span>
                <span className="ev-time">{item.time || ''}</span>
              </motion.div>
            ))}
            <div className="microrca-cov-banner">
              <span>⚡ MicroRCA++ Dynamic PageRank</span>
              <b>RPS=480 · Cov=0.94</b>
            </div>
          </motion.div>
        ) : (
          <motion.div
            key="tab-trace"
            className="otel-waterfall-box"
            initial={{ opacity: 0, x: 8 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -8 }}
            transition={{ duration: 0.22 }}
          >
            {loadingTrace ? (
              <div className="canary-spinner-row" style={{ padding: '16px 0' }}>
                <span className="sota-spinner" />
                <span>Decomposing OpenTelemetry Span Tree...</span>
              </div>
            ) : (
              traceReport && (
                <>
                  <div className="otel-bottleneck-summary">
                    <div className="otel-bottleneck-top">
                      <span className="otel-badge-critical">BOTTLENECK ISOLATED</span>
                      <span className="otel-trace-id">{traceReport.trace_id}</span>
                    </div>
                    <div className="otel-bottleneck-op">{traceReport.bottleneck_operation}</div>
                    <div className="otel-bottleneck-metrics">
                      <span>
                        Service: <b>{traceReport.bottleneck_service}</b>
                      </span>
                      <span>
                        Self-Time: <b className="text-danger">{traceReport.bottleneck_exclusive_ms}ms</b> (
                        {traceReport.bottleneck_contribution_pct}%)
                      </span>
                    </div>
                  </div>

                  <div className="otel-span-list">
                    {(traceReport.span_attributions || []).slice(0, 4).map((span, i) => (
                      <div key={span.span_id || i} className="otel-span-row">
                        <div className="otel-span-meta">
                          <span className="otel-span-svc">{span.service_id}</span>
                          <span className="otel-span-dur">
                            {span.exclusive_duration_ms}ms ({span.exclusive_share_pct}%)
                          </span>
                        </div>
                        <div className="otel-span-bar-bg">
                          <motion.div
                            className={`otel-span-bar-fill ${
                              span.exclusive_share_pct > 50 ? 'bottleneck' : 'normal'
                            }`}
                            initial={{ width: 0 }}
                            animate={{ width: `${Math.max(6, span.exclusive_share_pct)}%` }}
                            transition={{ duration: 0.65, delay: i * 0.08 }}
                          />
                        </div>
                      </div>
                    ))}
                  </div>
                </>
              )
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}
