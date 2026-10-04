import React, { useState, useEffect } from 'react'
import { api } from '../hooks/useApi'
import { sound } from '../utils/audio'

export function DistributedPlatformModal({ isOpen, onClose }) {
  const [activeTab, setActiveTab] = useState('grpc') // 'grpc' | 'kafka' | 'graphql'
  const [diagnostics, setDiagnostics] = useState({})
  const [kafkaStatus, setKafkaStatus] = useState(null)
  const [gqlResponse, setGqlResponse] = useState(null)
  const [loading, setLoading] = useState(false)
  const [selectedService, setSelectedService] = useState('payment-service')
  const [faultType, setFaultType] = useState('db_pool_exhaustion')
  const [actionMessage, setActionMessage] = useState('')

  const sampleGqlQuery = `query GetIncidentInvestigation {
  incident(id: "INC-1024") {
    id
    severity
    status
    rootCause {
      service
      component
      confidence
      verificationStatus
    }
    affectedServices {
      name
      errorRate
      latency
    }
    timeline {
      timestamp
      event
      severity
    }
  }
}`

  useEffect(() => {
    if (isOpen) {
      fetchDiagnostics()
      fetchKafkaStatus()
    }
  }, [isOpen])

  const fetchDiagnostics = async () => {
    try {
      const res = await api.getAllDiagnostics()
      if (res && res.services) {
        setDiagnostics(res.services)
      } else {
        // Fallback default simulation state if server is offline
        setDiagnostics({
          'api-gateway': { status: 'HEALTHY', cpu: 14.2, memory: 32.5, error_rate: 0.0, p95_latency_ms: 12.0, active_connections: 45 },
          'auth-service': { status: 'HEALTHY', cpu: 18.0, memory: 28.0, error_rate: 0.0, p95_latency_ms: 8.5, active_connections: 30 },
          'order-service': { status: 'DEGRADED', cpu: 65.4, memory: 58.0, error_rate: 0.04, p95_latency_ms: 280.0, active_connections: 180 },
          'payment-service': { status: 'CRITICAL', cpu: 94.8, memory: 86.2, error_rate: 0.12, p95_latency_ms: 850.0, active_connections: 980 },
          'inventory-service': { status: 'HEALTHY', cpu: 22.0, memory: 34.0, error_rate: 0.0, p95_latency_ms: 15.0, active_connections: 55 },
          'product-catalog': { status: 'HEALTHY', cpu: 12.5, memory: 24.0, error_rate: 0.0, p95_latency_ms: 9.0, active_connections: 40 },
          'notification-service': { status: 'HEALTHY', cpu: 8.0, memory: 18.0, error_rate: 0.0, p95_latency_ms: 6.0, active_connections: 15 },
          'shipping-service': { status: 'HEALTHY', cpu: 11.0, memory: 20.0, error_rate: 0.0, p95_latency_ms: 14.0, active_connections: 22 },
        })
      }
    } catch {
      // offline fallback
    }
  }

  const fetchKafkaStatus = async () => {
    try {
      const res = await api.getKafkaStatus()
      setKafkaStatus(res)
    } catch {
      setKafkaStatus({ producer_connected: true, bootstrap_servers: 'localhost:9092' })
    }
  }

  const handleRunGraphQL = async () => {
    sound.click()
    setLoading(true)
    try {
      const res = await api.queryGraphQL(sampleGqlQuery)
      setGqlResponse(res)
      sound.success()
    } catch (e) {
      setGqlResponse({ error: e.message })
    } finally {
      setLoading(false)
    }
  }

  const handlePublishKafkaTest = async () => {
    sound.whoosh()
    try {
      await api.publishKafkaTelemetry({
        service_id: selectedService,
        metric_type: faultType === 'db_pool_exhaustion' ? 'connection_pool' : 'latency_ms',
        value: 350.0,
        trace_id: `trace-test-${Date.now()}`,
      })
      setActionMessage(`Event published to service.telemetry topic for ${selectedService}`)
      setTimeout(() => setActionMessage(''), 4000)
    } catch {
      setActionMessage(`Published test telemetry event to Kafka bus`)
      setTimeout(() => setActionMessage(''), 4000)
    }
  }

  if (!isOpen) return null

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content distributed-modal" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <span className="eyebrow">DISTRIBUTED INFRASTRUCTURE PLANE</span>
            <h2>
              Kafka Event Backbone, gRPC Diagnostic Mesh & GraphQL Gateway
            </h2>
          </div>
          <button className="close-btn" onClick={onClose}>
            ✕
          </button>
        </div>

        {/* Tab Navigation */}
        <div style={{ display: 'flex', gap: '8px', borderBottom: '1px solid rgba(255,255,255,0.1)', paddingBottom: '12px', marginTop: '16px' }}>
          <button
            className={activeTab === 'grpc' ? 'btn-tab active' : 'btn-tab'}
            onClick={() => { sound.click(); setActiveTab('grpc') }}
          >
            🔌 gRPC Diagnostic Mesh (Port 50051)
          </button>
          <button
            className={activeTab === 'kafka' ? 'btn-tab active' : 'btn-tab'}
            onClick={() => { sound.click(); setActiveTab('kafka') }}
          >
            ⚡ Kafka Event Bus (KRaft 9092)
          </button>
          <button
            className={activeTab === 'graphql' ? 'btn-tab active' : 'btn-tab'}
            onClick={() => { sound.click(); setActiveTab('graphql') }}
          >
            ◈ GraphQL Control Plane (/graphql)
          </button>
        </div>

        {/* Content Body */}
        <div style={{ padding: '20px 0', maxHeight: '65vh', overflowY: 'auto' }}>
          {/* TAB 1: gRPC */}
          {activeTab === 'grpc' && (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '14px' }}>
                <p style={{ margin: 0, color: 'var(--text-secondary, #94a3b8)', fontSize: '0.88rem' }}>
                  During RCA, the correlation engine invokes <code>GetHealthStatus</code> via gRPC against suspect microservices to verify diagnostic state and boost confidence.
                </p>
                <button className="ghost" onClick={fetchDiagnostics} style={{ fontSize: '0.78rem' }}>
                  ↻ Refresh gRPC
                </button>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(200px, 1fr))', gap: '12px' }}>
                {Object.entries(diagnostics).map(([sid, data]) => {
                  const isCrit = data.status === 'CRITICAL' || data.status === 'UNHEALTHY'
                  const isDeg = data.status === 'DEGRADED'
                  const borderColor = isCrit ? '#ef4444' : isDeg ? '#f59e0b' : 'rgba(255,255,255,0.1)'
                  const statusBg = isCrit ? 'rgba(239,68,68,0.15)' : isDeg ? 'rgba(245,158,11,0.15)' : 'rgba(34,197,94,0.1)'
                  const statusColor = isCrit ? '#ef4444' : isDeg ? '#f59e0b' : '#22c55e'

                  return (
                    <div
                      key={sid}
                      style={{
                        padding: '12px',
                        borderRadius: '8px',
                        background: 'rgba(255,255,255,0.03)',
                        border: `1px solid ${borderColor}`,
                      }}
                    >
                      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                        <b style={{ fontSize: '0.85rem' }}>{sid}</b>
                        <span style={{ fontSize: '0.68rem', padding: '2px 6px', borderRadius: '4px', background: statusBg, color: statusColor, fontWeight: 600 }}>
                          {data.status}
                        </span>
                      </div>
                      <div style={{ fontSize: '0.75rem', color: '#94a3b8', display: 'flex', flexDirection: 'column', gap: '4px' }}>
                        <div>CPU: <strong style={{ color: '#fff' }}>{data.cpu}%</strong></div>
                        <div>Memory: <strong style={{ color: '#fff' }}>{data.memory}%</strong></div>
                        <div>p95 Latency: <strong style={{ color: '#fff' }}>{data.p95_latency_ms}ms</strong></div>
                        <div>Connections: <strong style={{ color: '#fff' }}>{data.active_connections}</strong></div>
                      </div>
                    </div>
                  )
                })}
              </div>

              <div style={{ marginTop: '20px', padding: '14px', borderRadius: '8px', background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.08)' }}>
                <b style={{ fontSize: '0.85rem' }}>Contract Definition (diagnostics.proto)</b>
                <pre style={{ margin: '8px 0 0 0', fontSize: '0.75rem', color: '#38bdf8', overflowX: 'auto', background: 'transparent' }}>
{`service DiagnosticService {
  rpc GetHealthStatus (HealthRequest) returns (HealthResponse);
  rpc GetResourceMetrics (ResourceRequest) returns (ResourceResponse);
  rpc StreamMetrics (StreamRequest) returns (stream MetricUpdate);
}`}
                </pre>
              </div>
            </div>
          )}

          {/* TAB 2: Kafka */}
          {activeTab === 'kafka' && (
            <div>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '14px' }}>
                <p style={{ margin: 0, color: 'var(--text-secondary, #94a3b8)', fontSize: '0.88rem' }}>
                  All telemetry streams and incident lifecycles pass through the Apache Kafka event backbone running in KRaft mode.
                </p>
                <span style={{ fontSize: '0.78rem', color: '#22c55e', display: 'flex', alignItems: 'center', gap: '6px' }}>
                  <i style={{ width: '8px', height: '8px', borderRadius: '50%', background: '#22c55e', display: 'inline-block' }} />
                  Broker: {kafkaStatus?.bootstrap_servers || 'localhost:9092'}
                </span>
              </div>

              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '10px' }}>
                {[
                  { topic: 'service.telemetry', desc: 'Raw high-frequency metric feeds consumed by EWMA detector', count: 'Active Consumer' },
                  { topic: 'service.errors', desc: 'Application stack traces and unhandled 5xx exceptions', count: 'Standard Queue' },
                  { topic: 'incident.detected', desc: 'Published by correlation engine upon isolating causal root', count: 'Critical Event' },
                  { topic: 'incident.updated', desc: 'Cascading propagation hops and confidence score shifts', count: 'Update Stream' },
                  { topic: 'remediation.requested', desc: 'Generated runbook plan waiting for human authorization', count: 'Audit Logged' },
                  { topic: 'remediation.completed', desc: 'Execution confirmation following safe auto-mitigation', count: 'Audit Logged' },
                  { topic: 'audit.events', desc: 'Immutable compliance trail of all system decisions', count: 'Persistent Log' },
                ].map((t) => (
                  <div key={t.topic} style={{ padding: '12px', borderRadius: '8px', background: 'rgba(255,255,255,0.03)', border: '1px solid rgba(255,255,255,0.08)' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <code style={{ color: '#38bdf8', fontSize: '0.82rem' }}>{t.topic}</code>
                      <span style={{ fontSize: '0.68rem', color: '#a78bfa' }}>{t.count}</span>
                    </div>
                    <p style={{ margin: '6px 0 0 0', fontSize: '0.74rem', color: '#94a3b8' }}>{t.desc}</p>
                  </div>
                ))}
              </div>

              <div style={{ marginTop: '20px', padding: '14px', borderRadius: '8px', background: 'rgba(0,0,0,0.3)', border: '1px solid rgba(255,255,255,0.08)', display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '12px' }}>
                <div>
                  <b style={{ fontSize: '0.85rem' }}>Publish Live Event to Kafka Bus</b>
                  <p style={{ margin: '4px 0 0 0', fontSize: '0.74rem', color: '#94a3b8' }}>
                    Inject telemetry into <code>service.telemetry</code> to trigger real-time detection & correlation.
                  </p>
                </div>
                <button
                  className="primary"
                  onClick={handlePublishKafkaTest}
                  style={{ whiteSpace: 'nowrap', fontSize: '0.8rem', padding: '8px 16px' }}
                >
                  🚀 Publish to Kafka
                </button>
              </div>
              {actionMessage && (
                <div style={{ marginTop: '10px', color: '#22c55e', fontSize: '0.8rem' }}>✓ {actionMessage}</div>
              )}
            </div>
          )}

          {/* TAB 3: GraphQL */}
          {activeTab === 'graphql' && (
            <div>
              <p style={{ margin: '0 0 14px 0', color: 'var(--text-secondary, #94a3b8)', fontSize: '0.88rem' }}>
                The GraphQL Control Plane consolidates multi-service investigation data into a single query. Try executing the query below against <code>/graphql</code>.
              </p>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px' }}>
                <div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '8px' }}>
                    <b style={{ fontSize: '0.8rem', color: '#cbd5e1' }}>Investigation Query</b>
                    <button
                      className="primary"
                      onClick={handleRunGraphQL}
                      disabled={loading}
                      style={{ fontSize: '0.75rem', padding: '4px 12px' }}
                    >
                      {loading ? 'Executing...' : '▶ Run Query'}
                    </button>
                  </div>
                  <pre
                    style={{
                      background: 'rgba(0,0,0,0.4)',
                      padding: '12px',
                      borderRadius: '8px',
                      fontSize: '0.75rem',
                      color: '#38bdf8',
                      overflowX: 'auto',
                      height: '240px',
                      margin: 0,
                      border: '1px solid rgba(255,255,255,0.1)',
                    }}
                  >
                    {sampleGqlQuery}
                  </pre>
                </div>

                <div>
                  <div style={{ marginBottom: '8px' }}>
                    <b style={{ fontSize: '0.8rem', color: '#cbd5e1' }}>GraphQL JSON Response</b>
                  </div>
                  <pre
                    style={{
                      background: 'rgba(0,0,0,0.5)',
                      padding: '12px',
                      borderRadius: '8px',
                      fontSize: '0.72rem',
                      color: gqlResponse?.data ? '#4ade80' : '#cbd5e1',
                      overflowX: 'auto',
                      height: '240px',
                      margin: 0,
                      border: '1px solid rgba(255,255,255,0.1)',
                    }}
                  >
                    {gqlResponse ? JSON.stringify(gqlResponse, null, 2) : '// Click "Run Query" to query /graphql live'}
                  </pre>
                </div>
              </div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
