import React, { useState } from 'react'
import { sound } from '../utils/audio'

const FLEET_SERVICES_DATA = {
  'api-gateway': {
    name: 'API Gateway',
    status: 'nominal',
    statusText: 'Healthy (200 OK)',
    replicas: '8 / 8 Running',
    cpu: '18.4%',
    memory: '342 MB',
    p99: '18ms',
    rps: '1,840 req/s',
    logs: [
      '[INFO] 19:55:01 HTTP 200 GET /api/v1/checkout/health - 12ms',
      '[INFO] 19:55:03 Ingress route balanced across 8 worker pods',
      '[INFO] 19:55:07 Rate limiter budget: 98% nominal capacity',
    ],
  },
  'auth-service': {
    name: 'Auth Service',
    status: 'nominal',
    statusText: 'Healthy (JWT Verified)',
    replicas: '4 / 4 Running',
    cpu: '12.1%',
    memory: '184 MB',
    p99: '11ms',
    rps: '420 req/s',
    logs: [
      '[INFO] 19:55:02 RS256 token verification cache hit (99.2%)',
      '[INFO] 19:55:04 OAuth2 introspection batch latency: 8ms',
    ],
  },
  'product-catalog': {
    name: 'Product Catalog',
    status: 'nominal',
    statusText: 'Healthy (Cache Warm)',
    replicas: '6 / 6 Running',
    cpu: '24.8%',
    memory: '512 MB',
    p99: '22ms',
    rps: '890 req/s',
    logs: [
      '[INFO] 19:55:01 Redis L2 item cache hit ratio: 94.6%',
      '[INFO] 19:55:05 Catalog query batch executed in 14ms',
    ],
  },
  'order-service': {
    name: 'Order Service',
    status: 'warning',
    statusText: 'Degraded (Cascade Latency)',
    replicas: '6 / 6 Running',
    cpu: '68.2%',
    memory: '640 MB',
    p99: '210ms',
    rps: '650 req/s',
    logs: [
      '[WARN] 19:55:02 Upstream payment-service response latency +380%',
      '[WARN] 19:55:06 HTTP 504 Gateway Timeout on /orders/checkout',
      '[WARN] 19:55:08 Circuit breaker half-open: retrying payment-service',
    ],
  },
  'payment-service': {
    name: 'Payment Service',
    status: 'critical',
    statusText: 'CRITICAL (Pool Exhaustion Origin)',
    replicas: '4 / 4 Running (Saturated)',
    cpu: '91.4%',
    memory: '920 MB',
    p99: '1,450ms',
    rps: '380 req/s',
    logs: [
      '[ERROR] 19:55:00 Connection pool saturated: 50/50 active connections',
      '[ERROR] 19:55:03 HikariPool-1 - Connection acquisition timeout (30,000ms)',
      '[ERROR] 19:55:05 Postgres server holding 48 locks on checkout_ledger',
      '[FATAL] 19:55:09 Root Cause Isolated by EWMA Engine (z=+4.82)',
    ],
  },
  'inventory-service': {
    name: 'Inventory Service',
    status: 'nominal',
    statusText: 'Healthy (Locks Released)',
    replicas: '4 / 4 Running',
    cpu: '15.3%',
    memory: '220 MB',
    p99: '14ms',
    rps: '310 req/s',
    logs: [
      '[INFO] 19:55:02 Stock reservation completed for SKU-904',
      '[INFO] 19:55:06 Pessimistic row locks released in 3ms',
    ],
  },
  'notification-service': {
    name: 'Notification Service',
    status: 'nominal',
    statusText: 'Healthy (Queue Drained)',
    replicas: '3 / 3 Running',
    cpu: '8.4%',
    memory: '140 MB',
    p99: '4ms',
    rps: '120 req/s',
    logs: [
      '[INFO] 19:55:01 SQS worker polled 42 email dispatch jobs',
      '[INFO] 19:55:04 Webhook retry queue lag: 0ms',
    ],
  },
  'shipping-service': {
    name: 'Shipping Service',
    status: 'nominal',
    statusText: 'Healthy (Nominal)',
    replicas: '3 / 3 Running',
    cpu: '9.2%',
    memory: '160 MB',
    p99: '16ms',
    rps: '95 req/s',
    logs: [
      '[INFO] 19:55:03 Tracking carrier API webhook delivered',
      '[INFO] 19:55:07 Label generator worker nominal',
    ],
  },
}

export function UserProfileModal({
  isOpen,
  onClose,
  userName = 'Alex Rivera',
  onUpdateUserName,
  onSelectService,
  onInjectChaos,
}) {
  const [activeTab, setActiveTab] = useState('profile')
  const [selectedFleetService, setSelectedFleetService] = useState('payment-service')
  const [editingName, setEditingName] = useState(userName)
  const [autoRemediation, setAutoRemediation] = useState(true)
  const [soundEffects, setSoundEffects] = useState(true)
  const [copiedKey, setCopiedKey] = useState(false)
  const [saveSuccess, setSaveSuccess] = useState(false)

  if (!isOpen) return null

  const handleCopyKey = () => {
    navigator.clipboard.writeText('aiops_live_sec_89f2a93c71e041bd882e')
    setCopiedKey(true)
    sound.success()
    setTimeout(() => setCopiedKey(false), 2000)
  }

  const handleSaveName = (e) => {
    e.preventDefault()
    if (!editingName.trim()) return
    sound.success()
    if (onUpdateUserName) onUpdateUserName(editingName.trim())
    setSaveSuccess(true)
    setTimeout(() => setSaveSuccess(false), 2500)
  }

  const initials = (userName || 'Alex Rivera')
    .split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2) || 'AR'

  const currentSvc = FLEET_SERVICES_DATA[selectedFleetService] || FLEET_SERVICES_DATA['payment-service']

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-content profile-modal-content" onClick={(e) => e.stopPropagation()}>
        {/* Header */}
        <div className="modal-header">
          <div className="profile-header-left">
            <div className="profile-avatar-large">
              <div className="avatar-gradient">{initials}</div>
              <span className="avatar-online-dot" />
            </div>
            <div>
              <h3>{userName}</h3>
              <div className="profile-role-badge">Lead SRE · Incident Commander</div>
            </div>
          </div>
          <button className="close-btn" onClick={onClose}>✕</button>
        </div>

        {/* Tab Navigation */}
        <div className="profile-tabs">
          <button
            className={`profile-tab ${activeTab === 'profile' ? 'active' : ''}`}
            onClick={() => { sound.click(); setActiveTab('profile') }}
          >
            👤 Commander Profile & Identity
          </button>
          <button
            className={`profile-tab ${activeTab === 'cluster' ? 'active' : ''}`}
            onClick={() => { sound.click(); setActiveTab('cluster') }}
          >
            ☸️ Cluster & Fleet (Interactive)
          </button>
          <button
            className={`profile-tab ${activeTab === 'api' ? 'active' : ''}`}
            onClick={() => { sound.click(); setActiveTab('api') }}
          >
            🔑 API Tokens & Security
          </button>
        </div>

        {/* Tab 1: Profile, Identity & Name Editing */}
        {activeTab === 'profile' && (
          <div className="profile-tab-body">
            {/* Identity Name Setting Form */}
            <div className="profile-name-edit-box">
              <h4>Commander Identity Settings</h4>
              <form onSubmit={handleSaveName} className="name-edit-form">
                <div className="name-input-group">
                  <label>Change Display Name:</label>
                  <div className="name-input-row">
                    <input
                      type="text"
                      className="name-text-input"
                      value={editingName}
                      onChange={(e) => setEditingName(e.target.value)}
                      placeholder="Enter your name (e.g. Alex Rivera)"
                    />
                    <button type="submit" className="save-name-btn">
                      {saveSuccess ? '✓ Saved' : 'Update Name'}
                    </button>
                  </div>
                  {saveSuccess && (
                    <span className="name-saved-msg">✓ Commander identity updated across dashboard!</span>
                  )}
                </div>
              </form>
            </div>

            <div className="profile-stats-grid">
              <div className="p-stat-card">
                <small>CLUSTER ROLE</small>
                <b>ClusterAdmin</b>
                <span className="p-subtext green">Full Root Privileges</span>
              </div>
              <div className="p-stat-card">
                <small>MTTR RESOLUTION</small>
                <b>0.78s</b>
                <span className="p-subtext blue">Top 1% Response Speed</span>
              </div>
              <div className="p-stat-card">
                <small>RCA ACCURACY</small>
                <b>100.0%</b>
                <span className="p-subtext green">30/30 Benchmarks</span>
              </div>
              <div className="p-stat-card">
                <small>SESSION ID</small>
                <b>#SRE-9482</b>
                <span className="p-subtext amber">prod-us-east-1</span>
              </div>
            </div>

            <div className="profile-settings-section">
              <h4>System Preferences</h4>
              <div className="setting-row">
                <div>
                  <b>Autonomous Remediation Guardrails</b>
                  <p>Require human approval for destructive container restarts and rollback operations.</p>
                </div>
                <input
                  type="checkbox"
                  checked={autoRemediation}
                  onChange={(e) => {
                    setAutoRemediation(e.target.checked)
                    sound.click()
                  }}
                />
              </div>

              <div className="setting-row">
                <div>
                  <b>Haptic Web Audio Synthesizer</b>
                  <p>Play cinematic auditory cues on telemetry spikes and anomaly correlations.</p>
                </div>
                <input
                  type="checkbox"
                  checked={soundEffects}
                  onChange={(e) => {
                    setSoundEffects(e.target.checked)
                    sound.click()
                  }}
                />
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Interactive Cluster & Fleet Inspector */}
        {activeTab === 'cluster' && (
          <div className="profile-tab-body">
            <div className="cluster-info-card">
              <div className="cluster-row">
                <span>Active Target Cluster:</span>
                <b>kubernetes.prod-us-east-1.k8s.io (v1.29.4)</b>
              </div>
              <div className="cluster-row">
                <span>Telemetry Ingress:</span>
                <b className="green">OpenTelemetry gRPC (Port 4317) · Live Streaming</b>
              </div>
              <div className="cluster-row">
                <span>Vector Embeddings:</span>
                <b className="blue">PostgreSQL 16 pgvector (7-dim Cosine Index)</b>
              </div>
            </div>

            <div className="fleet-nodes-list">
              <h4>Monitored Microservices — Click Any Service to Inspect & Filter</h4>
              <div className="fleet-pills">
                {Object.keys(FLEET_SERVICES_DATA).map((sId) => {
                  const s = FLEET_SERVICES_DATA[sId]
                  const isSelected = selectedFleetService === sId
                  const isWarn = s.status === 'warning'
                  const isCrit = s.status === 'critical'

                  return (
                    <button
                      key={sId}
                      className={`f-pill-btn ${isSelected ? 'selected' : ''} ${isCrit ? 'critical' : isWarn ? 'warn' : 'nominal'}`}
                      onClick={() => {
                        sound.click()
                        setSelectedFleetService(sId)
                      }}
                      title={`Click to inspect ${s.name}`}
                    >
                      <span className={`f-dot ${isCrit ? 'dot-crit' : isWarn ? 'dot-warn' : 'dot-nom'}`} />
                      {sId}
                    </button>
                  )
                })}
              </div>
            </div>

            {/* Live Service Inspector Card */}
            <div className="service-inspector-card">
              <div className="s-insp-head">
                <div>
                  <span className="eyebrow">LIVE TELEMETRY INSPECTOR</span>
                  <h3>{currentSvc.name}</h3>
                </div>
                <span className={`s-status-badge ${currentSvc.status}`}>
                  {currentSvc.statusText}
                </span>
              </div>

              <div className="s-metrics-grid">
                <div className="s-m-cell">
                  <small>REPLICAS</small>
                  <b>{currentSvc.replicas}</b>
                </div>
                <div className="s-m-cell">
                  <small>CPU USAGE</small>
                  <b className={currentSvc.status === 'critical' ? 'amber-text' : ''}>{currentSvc.cpu}</b>
                </div>
                <div className="s-m-cell">
                  <small>MEMORY</small>
                  <b>{currentSvc.memory}</b>
                </div>
                <div className="s-m-cell">
                  <small>P99 LATENCY</small>
                  <b className={currentSvc.status === 'critical' ? 'amber-text' : ''}>{currentSvc.p99}</b>
                </div>
              </div>

              {/* Real-time Pod Logs Console */}
              <div className="s-logs-console">
                <div className="s-logs-title">Pod Logs (STDOUT / OpenTelemetry):</div>
                {currentSvc.logs.map((log, idx) => (
                  <div key={idx} className={`s-log-line ${log.includes('ERROR') || log.includes('FATAL') ? 'log-err' : log.includes('WARN') ? 'log-warn' : 'log-info'}`}>
                    {log}
                  </div>
                ))}
              </div>

              {/* Actions */}
              <div className="s-insp-actions">
                <button
                  className="insp-action-btn primary"
                  onClick={() => {
                    sound.success()
                    if (onSelectService) onSelectService(currentSvc.name)
                    onClose()
                  }}
                >
                  🔍 Inspect on Dashboard Topology
                </button>
                <button
                  className="insp-action-btn secondary"
                  onClick={() => {
                    sound.alert()
                    if (onInjectChaos) onInjectChaos(selectedFleetService)
                    if (onSelectService) onSelectService(currentSvc.name)
                    onClose()
                  }}
                >
                  🔥 Inject Failure on {currentSvc.name}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Tab 3: API & Security */}
        {activeTab === 'api' && (
          <div className="profile-tab-body">
            <div className="api-key-box">
              <label>AIOps Root Cause Correlator — Master Access Token</label>
              <div className="api-key-input-wrap">
                <input
                  type="password"
                  readOnly
                  value="aiops_live_sec_89f2a93c71e041bd882e"
                  className="api-key-field"
                />
                <button className="copy-key-btn" onClick={handleCopyKey}>
                  {copiedKey ? '✓ Copied' : '📋 Copy Token'}
                </button>
              </div>
              <small>Use this Bearer token in your CI/CD deployment hooks and Prometheus Alertmanager endpoints.</small>
            </div>

            <div className="security-badges">
              <span className="sec-badge">🔒 mTLS Enforced</span>
              <span className="sec-badge">🛡️ RBAC: Admin</span>
              <span className="sec-badge">⚡ Rate Limit: 10,000 req/min</span>
            </div>
          </div>
        )}

        <div className="modal-footer">
          <button className="done-btn" onClick={onClose}>
            Done & Save Preferences
          </button>
        </div>
      </div>
    </div>
  )
}
