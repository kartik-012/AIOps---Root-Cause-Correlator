import React from 'react'
import { sound } from '../utils/audio'

export function IncidentSidebar({
  incidents,
  selectedIncidentId,
  onSelectIncident,
  selectedService,
  onSelectService,
  onRunCorrelation,
  onOpenEvaluation,
}) {
  const serviceList = [
    { name: 'API Gateway', status: 'nominal', subtitle: 'Nominal · 99.99%' },
    { name: 'Order Service', status: 'warn', subtitle: 'Elevated latency' },
    { name: 'Payment Service', status: 'warn', subtitle: 'Upstream impact' },
    { name: 'Postgres Primary', status: 'warn', subtitle: 'Connection saturation' },
    { name: 'Notification', status: 'dim', subtitle: 'Healthy' },
  ]

  return (
    <aside className="panel sidebar-panel">
      {/* Top Scrollable / Stack Section */}
      <div className="sidebar-top-section">
        {/* Active Incidents Section */}
        <div className="cap">ACTIVE INCIDENTS · 03</div>

        <div
          className={`incident-card ${selectedIncidentId === 'inc-1' || !selectedIncidentId || selectedIncidentId === 'inc-default' ? 'active' : 'inactive'}`}
          onClick={() => {
            sound.click()
            if (onSelectIncident) onSelectIncident('inc-default')
          }}
        >
          <div className="tag">P1 · INVESTIGATING</div>
          <h3>Checkout degradation</h3>
          <p>12 services correlated · 14 min ago</p>
        </div>

        <div
          className={`incident-card ${selectedIncidentId === 'inc-2' ? 'active' : 'inactive'}`}
          onClick={() => {
            sound.click()
            if (onSelectIncident) onSelectIncident('inc-2')
          }}
        >
          <div className="tag dim-tag">P2 · MONITORING</div>
          <h3>Search latency</h3>
          <p>3 services correlated · 31 min ago</p>
        </div>

        {/* Service Health Section */}
        <div className="cap" style={{ marginTop: '22px' }}>
          SERVICE HEALTH (CLICK TO INSPECT)
        </div>

        <div className="service-health-list">
          {serviceList.map((s) => {
            const isSelected = (selectedService || '').toLowerCase().includes(s.name.toLowerCase())
            return (
              <div
                key={s.name}
                className={`serv-row ${isSelected ? 'selected' : ''}`}
                onClick={() => {
                  sound.click()
                  if (onSelectService) onSelectService(s.name)
                }}
                title={`Click to inspect ${s.name}`}
              >
                <i className={`dot ${s.status}`} />
                <div>
                  <b>{s.name}</b>
                  <p>{s.subtitle}</p>
                </div>
              </div>
            )
          })}
        </div>
      </div>

      {/* Bottom Fixed Action Section */}
      <div className="sidebar-bottom-section">
        <button
          className="correlate-btn-glass"
          onClick={() => {
            sound.whoosh()
            if (onRunCorrelation) onRunCorrelation()
          }}
        >
          ⚡ Run Live Correlation
        </button>

        <div
          className="bottom-cap cap clickable-cap"
          onClick={() => {
            sound.click()
            if (onOpenEvaluation) onOpenEvaluation()
          }}
          title="Open Synthetic Benchmark Evaluation Suite"
        >
          ◌ 24 HISTORICAL MATCHES ↗
        </div>
      </div>
    </aside>
  )
}
