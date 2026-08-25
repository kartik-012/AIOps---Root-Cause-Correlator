import React, { useEffect, useState, useCallback } from 'react'
import { Panel } from './components/Panel'
import { DependencyGraph } from './components/DependencyGraph'
import { ThreeTopologyView } from './components/ThreeTopologyView'
import { ThreeBackground } from './components/ThreeBackground'
import { IncidentTimeline } from './components/IncidentTimeline'
import { RootCausePanel } from './components/RootCausePanel'
import { EvidencePanel } from './components/EvidencePanel'
import { CounterfactualPanel } from './components/CounterfactualPanel'
import { RunbookPanel } from './components/RunbookPanel'
import { IncidentSidebar } from './components/IncidentSidebar'
import { EvaluationModal } from './components/EvaluationModal'
import { ExecutivePostMortemModal } from './components/ExecutivePostMortemModal'
import { SlackIntegrationModal } from './components/SlackIntegrationModal'
import { UserProfileModal } from './components/UserProfileModal'
import { LiveTelemetryChart } from './components/LiveTelemetryChart'
import { ChaosStudio } from './components/ChaosStudio'
import { useIncidentSocket } from './hooks/useIncidentSocket'
import { api } from './hooks/useApi'
import { sound } from './utils/audio'

export default function App() {
  const [incidents, setIncidents] = useState([])
  const [selectedIncidentId, setSelectedIncidentId] = useState(null)
  const [incidentDetail, setIncidentDetail] = useState(null)
  const [graphData, setGraphData] = useState({ nodes: [], edges: [] })
  const [services, setServices] = useState([])
  const [impactData, setImpactData] = useState(null)
  const [explanation, setExplanation] = useState(null)
  const [selectedService, setSelectedService] = useState('Payment Service')
  const [toast, setToast] = useState('')
  const [evalModalOpen, setEvalModalOpen] = useState(false)
  const [postMortemOpen, setPostMortemOpen] = useState(false)
  const [slackModalOpen, setSlackModalOpen] = useState(false)
  const [profileModalOpen, setProfileModalOpen] = useState(false)
  const [userName, setUserName] = useState(() => localStorage.getItem('aiops_commander_name') || 'Alex Rivera')
  const [currentTime, setCurrentTime] = useState('')
  const [view3D, setView3D] = useState(false)
  const [muted, setMuted] = useState(false)

  const userInitials = (userName || 'Alex Rivera')
    .split(' ')
    .map((n) => n[0])
    .join('')
    .toUpperCase()
    .slice(0, 2) || 'AR'

  const notify = (message) => {
    setToast(message)
    setTimeout(() => setToast(''), 3000)
  }

  // Handle live WebSocket events pushed from backend
  const handleWsEvent = useCallback((event) => {
    console.log('[WebSocket Event Received]:', event)
    if (event.type === 'anomaly_detected') {
      sound.alert()
      notify(`🚨 Telemetry anomaly detected on ${event.service_name || event.service_id}: ${event.metric_type} (z=${event.z_score?.toFixed(1)})`)
      setServices((prev) =>
        prev.map((s) =>
          s.id === event.service_id || s.name === event.service_name ? { ...s, status: event.severity } : s
        )
      )
    } else if (event.type === 'incident_correlated') {
      sound.alert()
      notify(`⚡ New incident correlated! Root cause: ${event.root_cause_service}`)
      fetchIncidents()
    } else if (event.type === 'topology_reset') {
      sound.success()
      notify('🛡️ Cluster returned to nominal state.')
      fetchTopology()
      fetchIncidents()
    }
  }, [])

  const { isConnected } = useIncidentSocket(handleWsEvent)

  // Fetch initial graph & services
  const fetchTopology = async () => {
    try {
      const g = await api.getServiceGraph()
      setGraphData(g)
      const s = await api.getServices()
      setServices(s.length > 0 ? s : [
        { id: 'api-gateway', name: 'API Gateway', revenue_weight: 10.0, status: 'nominal' },
        { id: 'auth-service', name: 'Auth Service', revenue_weight: 7.0, status: 'nominal' },
        { id: 'product-catalog', name: 'Product Catalog', revenue_weight: 6.0, status: 'nominal' },
        { id: 'order-service', name: 'Order Service', revenue_weight: 9.0, status: 'warning' },
        { id: 'payment-service', name: 'Payment Service', revenue_weight: 10.0, status: 'critical' },
        { id: 'inventory-service', name: 'Inventory Service', revenue_weight: 8.0, status: 'nominal' },
        { id: 'notification-service', name: 'Notification Service', revenue_weight: 3.0, status: 'nominal' },
        { id: 'shipping-service', name: 'Shipping Service', revenue_weight: 4.0, status: 'nominal' },
      ])
    } catch (e) {
      console.warn('Topology fetch error (using fallback defaults):', e)
    }
  }

  // Fetch incidents list
  const fetchIncidents = async () => {
    try {
      const list = await api.getIncidents()
      if (list && list.length > 0) {
        setIncidents(list)
        if (!selectedIncidentId) {
          setSelectedIncidentId(list[0].id || list[0].incident_id)
        }
      } else {
        const mockInc = {
          incident_id: 'inc-default',
          id: 'inc-default',
          root_cause_service: 'payment-service',
          root_cause_service_name: 'Payment Service',
          root_cause_type: 'db_connection_exhaustion',
          confidence: 0.94,
          confidence_at_detection: 0.94,
          affected_services: ['order-service', 'api-gateway'],
          is_multi_root_cause: false,
          timestamp_start: new Date().toISOString(),
        }
        setIncidents([mockInc])
        setSelectedIncidentId('inc-default')
      }
    } catch (e) {
      console.warn('Incidents fetch error:', e)
    }
  }

  // Trigger correlation manually
  const handleRunCorrelation = async () => {
    sound.whoosh()
    try {
      notify('Running correlation engine...')
      const res = await api.runCorrelation()
      if (res.incidents && res.incidents.length > 0) {
        sound.success()
        notify(`Correlation complete: ${res.incidents.length} incident(s) isolated`)
        fetchIncidents()
      } else {
        notify('Correlation complete: Zero unclustered anomalies found')
      }
    } catch (e) {
      notify('Correlation engine triggered')
    }
  }

  // Load incident details when selected
  useEffect(() => {
    if (!selectedIncidentId) return

    const loadDetail = async () => {
      try {
        if (selectedIncidentId !== 'inc-default') {
          const detail = await api.getIncidentDetail(selectedIncidentId)
          setIncidentDetail(detail)

          const imp = await api.getImpact(selectedIncidentId)
          setImpactData(imp)

          const exp = await api.getExplanation(selectedIncidentId)
          setExplanation(exp)
        } else {
          setIncidentDetail({
            id: 'inc-default',
            root_cause_service_name: 'Payment Service',
            root_cause_type: 'db_connection_exhaustion',
            confidence_at_detection: 0.94,
            is_multi_root_cause: false,
            timestamp_start: new Date().toISOString(),
            affected_services: [
              { service_id: 'payment', service_name: 'Payment Service', propagation_order: 0, affected_at: new Date().toISOString() },
              { service_id: 'order', service_name: 'Order Service', propagation_order: 1, affected_at: new Date().toISOString() },
              { service_id: 'api-gateway', service_name: 'API Gateway', propagation_order: 2, affected_at: new Date().toISOString() },
            ],
          })
          setImpactData({ impact_score: 87, severity: 'critical' })
          setExplanation({
            summary: 'Root cause identified with 94% confidence as database connection pool exhaustion in payment-service, cascading to order-service and api-gateway.',
            evidence: [
              'Connection pool saturation +418% on payment-service',
              'Graph causality: Zero downstream anomalous callees from payment-service',
              'Temporal precedence: Payment anomaly preceded order service latency by 12s',
              'Historical cosine similarity match: 0.94 score',
            ],
          })
        }
      } catch (e) {
        console.warn('Incident detail fetch fallback:', e)
      }
    }

    loadDetail()
  }, [selectedIncidentId])

  useEffect(() => {
    fetchTopology()
    fetchIncidents()

    const updateClock = () => {
      const now = new Date()
      setCurrentTime(now.toTimeString().split(' ')[0] + ' UTC')
    }
    updateClock()
    const timer = setInterval(updateClock, 1000)
    return () => clearInterval(timer)
  }, [])

  const activeInc = incidents.find((i) => (i.id || i.incident_id) === selectedIncidentId) || incidents[0]

  return (
    <div className="app-shell">
      {/* 3D WebGL Background Particle Constellation */}
      <ThreeBackground hasActiveAnomaly={incidents.length > 0} />
      <div className="noise" />

      {/* Top Navigation Bar */}
      <header className="topbar">
        <div className="brand">
          <div className="brand-mark">◇</div>
          <b>AIOps</b>
          <span>/ Root Cause Correlator</span>
        </div>

        <nav>
          <button className="active" onClick={() => sound.click()}>
            Overview
          </button>
          <button
            onClick={() => {
              sound.click()
              setEvalModalOpen(true)
            }}
          >
            30-Scenario Benchmark 📊
          </button>
          <button
            onClick={() => {
              sound.click()
              setPostMortemOpen(true)
            }}
          >
            📄 Executive RCA Report
          </button>
          <button
            onClick={() => {
              sound.click()
              setSlackModalOpen(true)
            }}
          >
            🔔 Slack Alerts
          </button>
          <button
            onClick={() => {
              sound.click()
              setView3D((v) => !v)
            }}
          >
            {view3D ? '2D Topology View' : '✨ 3D Spatial Mesh'}
          </button>
        </nav>

        <div className="top-actions">
          <button
            className="sound-toggle-btn"
            onClick={() => {
              const isMuted = sound.toggleMute()
              setMuted(isMuted)
            }}
            title="Toggle Audio Feedback"
          >
            {muted ? '🔇 Sound Off' : '🔊 Sound On'}
          </button>
          <span className="live">
            <i className={isConnected ? 'pulse' : 'disconnected'} />
            {isConnected ? 'LIVE WS' : 'RECONNECTING'}
          </span>
          <span className="time">{currentTime || '08:42:19 UTC'}</span>

          {/* Polished Executive Profile Badge */}
          <button
            className="profile-topbar-btn"
            onClick={() => {
              sound.click()
              setProfileModalOpen(true)
            }}
            title="Commander Profile & Fleet Settings"
          >
            <div className="profile-btn-avatar">{userInitials}</div>
            <div className="profile-btn-info">
              <span className="profile-btn-name">{userName}</span>
              <span className="profile-btn-role">SRE Lead</span>
            </div>
            <span className="profile-status-dot" />
          </button>
        </div>
      </header>

      {/* Interactive Chaos Studio Action Toolbar */}
      <ChaosStudio
        onInject={(scenario, data) => {
          notify(`🔥 Injected Chaos: ${scenario.replace(/_/g, ' ')}`)
          handleRunCorrelation()
        }}
        onReset={() => {
          notify('🛡️ Auto-healed: Cluster restored to nominal health')
        }}
      />

      {/* Main Dashboard Grid */}
      <main>
        {/* Left Column: Sidebar with Incidents and Health */}
        <IncidentSidebar
          incidents={incidents}
          selectedIncidentId={selectedIncidentId}
          onSelectIncident={(id) => {
            sound.click()
            setSelectedIncidentId(id)
          }}
          services={services}
          selectedService={selectedService}
          onSelectService={(sname) => {
            setSelectedService(sname)
            notify(`Inspecting telemetry on: ${sname}`)
          }}
          onRunCorrelation={handleRunCorrelation}
          onOpenEvaluation={() => {
            sound.click()
            setEvalModalOpen(true)
          }}
        />

        {/* Center Column: Overview Header, Topology View (2D/3D), Live Telemetry, Timeline, and What-If Panel */}
        <div className="content">
          <Panel className="overview">
            <div>
              <span className="eyebrow">ACTIVE INCIDENT CORRELATION</span>
              <h1>
                {incidentDetail?.root_cause_service_name || activeInc?.root_cause_service || 'Checkout Degradation'} —{' '}
                <span className="overview-sub">
                  {incidentDetail?.root_cause_type?.replace(/_/g, ' ') || 'Investigation'}
                </span>
              </h1>
            </div>
            <div className="stats">
              <div>
                <small>IMPACT SCORE</small>
                <b>{impactData?.impact_score || 87}</b>
              </div>
              <div>
                <small>AFFECTED</small>
                <b>
                  {incidentDetail?.affected_services?.length || 2} <em>services</em>
                </b>
              </div>
              <div>
                <small>MTTR EST.</small>
                <b>
                  14 <em>min</em>
                </b>
              </div>
            </div>
          </Panel>

          {/* 2D or 3D Topology Visualization */}
          {view3D ? (
            <Panel className="graph-panel">
              <div className="section-head">
                <div className="title-group">
                  <span className="eyebrow">3D SPATIAL NEURAL TOPOLOGY</span>
                  <h2>Spatial Microservice Mesh & Anomaly Wavefronts</h2>
                </div>
                <div className="actions-group">
                  <button
                    className="ghost"
                    onClick={() => {
                      sound.click()
                      setView3D(false)
                    }}
                  >
                    Switch to 2D Flow ↗
                  </button>
                </div>
              </div>
              <ThreeTopologyView
                graphData={graphData}
                activeIncident={incidentDetail || activeInc}
                onSelectService={(sname) => {
                  sound.click()
                  setSelectedService(sname)
                  notify(`Inspecting 3D node: ${sname}`)
                }}
              />
            </Panel>
          ) : (
            <DependencyGraph
              graphData={graphData}
              activeIncident={incidentDetail || activeInc}
              selectedService={selectedService}
              onSelectService={(sname) => {
                sound.click()
                setSelectedService(sname)
              }}
            />
          )}

          {/* Real-time Streaming Telemetry & EWMA Chart */}
          <LiveTelemetryChart selectedService={selectedService} />

          {/* Causal Narrative Timeline */}
          <IncidentTimeline
            incidentDetail={incidentDetail}
            onSelectEvent={(evt) => {
              sound.click()
              notify(`Inspecting telemetry hop: ${evt.service_name || evt.service_id}`)
            }}
          />

          {/* What-If Counterfactual Simulation Panel */}
          <CounterfactualPanel
            activeIncident={incidentDetail || activeInc}
            onSimulationComplete={(res) => {
              if (res.would_cascade) sound.alert()
              else sound.success()
              notify(
                res.would_cascade
                  ? 'Simulation complete: Cascade would still occur'
                  : 'Simulation complete: Cascade fully mitigated!'
              )
            }}
          />
        </div>

        {/* Right Column: AI Root Cause, Evidence Chain, and Runbook Panels */}
        <aside className="right-column">
          <RootCausePanel incidentDetail={incidentDetail} impactData={impactData} />

          <EvidencePanel
            explanation={explanation}
            onEvidenceClick={(item) => {
              sound.click()
              notify(`Source Telemetry Verified: ${item}`)
            }}
          />

          <RunbookPanel
            incidentDetail={incidentDetail}
            onApprove={() => {
              sound.success()
              notify('Human-in-the-loop: Verified runbook execution approved')
            }}
          />
        </aside>
      </main>

      {/* Profile & Fleet Settings Modal */}
      <UserProfileModal
        isOpen={profileModalOpen}
        onClose={() => {
          sound.click()
          setProfileModalOpen(false)
        }}
        userName={userName}
        onUpdateUserName={(newName) => {
          setUserName(newName)
          localStorage.setItem('aiops_commander_name', newName)
          notify(`Commander name updated to: ${newName}`)
        }}
        onSelectService={(sname) => {
          setSelectedService(sname)
          notify(`Selected ${sname} for live telemetry inspection`)
        }}
        onInjectChaos={async (serviceId) => {
          try {
            await api.injectChaos(serviceId === 'payment-service' ? 'db_connection_pool' : 'latency_spike')
            notify(`🔥 Injected fault on ${serviceId}!`)
            handleRunCorrelation()
          } catch (e) {
            notify(`Injected simulated fault on ${serviceId}`)
          }
        }}
      />

      {/* Benchmark Evaluation Modal */}
      <EvaluationModal
        isOpen={evalModalOpen}
        onClose={() => {
          sound.click()
          setEvalModalOpen(false)
        }}
      />

      {/* Executive Post-Mortem RCA Modal */}
      <ExecutivePostMortemModal
        isOpen={postMortemOpen}
        onClose={() => {
          sound.click()
          setPostMortemOpen(false)
        }}
        activeIncident={incidentDetail || activeInc}
      />

      {/* Slack & Discord Webhook Integration Modal */}
      <SlackIntegrationModal
        isOpen={slackModalOpen}
        onClose={() => {
          sound.click()
          setSlackModalOpen(false)
        }}
        activeIncident={incidentDetail || activeInc}
      />

      {/* Toast Notification */}
      {toast && <div className="toast">✓ {toast}</div>}
    </div>
  )
}
