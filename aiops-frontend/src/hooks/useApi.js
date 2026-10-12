export const RAW_BASE = import.meta.env.VITE_API_URL || ''
export const API_BASE = RAW_BASE ? `${RAW_BASE.replace(/\/$/, '')}/api/v1` : '/api/v1'
export const GRAPHQL_BASE = RAW_BASE ? `${RAW_BASE.replace(/\/$/, '')}/graphql` : '/graphql'

export const api = {
  async getServices() {
    const res = await fetch(`${API_BASE}/services`)
    return res.json()
  },

  async getServiceGraph() {
    const res = await fetch(`${API_BASE}/services/graph`)
    return res.json()
  },

  async getIncidents() {
    const res = await fetch(`${API_BASE}/incidents`)
    return res.json()
  },

  async getIncidentDetail(id) {
    const res = await fetch(`${API_BASE}/correlation/incidents/${id}`)
    return res.json()
  },

  async runCorrelation() {
    const res = await fetch(`${API_BASE}/correlation/run`, { method: 'POST' })
    return res.json()
  },

  async getBlastRadius(id) {
    const res = await fetch(`${API_BASE}/prediction/blast-radius/${id}`)
    return res.json()
  },

  async simulateCounterfactual(incidentId, modifiedParam) {
    const res = await fetch(`${API_BASE}/counterfactual/simulate`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        incident_id: incidentId,
        modified_parameter: modifiedParam,
      }),
    })
    return res.json()
  },

  async getImpact(id) {
    const res = await fetch(`${API_BASE}/impact/${id}`)
    return res.json()
  },

  async getRunbook(rootCauseType) {
    const res = await fetch(`${API_BASE}/runbook/${rootCauseType}`)
    return res.json()
  },

  async approveRunbook(id) {
    const res = await fetch(`${API_BASE}/runbook/${id}/approve`, { method: 'POST' })
    return res.json()
  },

  async getExplanation(id) {
    const res = await fetch(`${API_BASE}/explain/${id}`, { method: 'POST' })
    return res.json()
  },

  async runEvaluationScenarios() {
    const res = await fetch(`${API_BASE}/eval/run-scenarios`, { method: 'POST' })
    return res.json()
  },

  async ingestMetric(payload) {
    const res = await fetch(`${API_BASE}/detection/ingest`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    return res.json()
  },

  // gRPC Diagnostics
  async getServiceHealth(serviceId) {
    const res = await fetch(`${API_BASE}/diagnostics/${serviceId}/health`)
    return res.json()
  },

  async getAllDiagnostics() {
    const res = await fetch(`${API_BASE}/diagnostics/all`)
    return res.json()
  },

  // Kafka Event Bus
  async getKafkaStatus() {
    const res = await fetch(`${API_BASE}/kafka/status`)
    return res.json()
  },

  async publishKafkaTelemetry(payload) {
    const res = await fetch(`${API_BASE}/kafka/publish-telemetry`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    })
    return res.json()
  },

  // GraphQL Gateway
  async queryGraphQL(query, variables = {}) {
    const res = await fetch(GRAPHQL_BASE, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, variables }),
    })
    return res.json()
  },

  // Chaos Studio
  async injectChaos(scenario) {
    const res = await fetch(`${API_BASE}/chaos/inject`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario }),
    })
    return res.json()
  },

  // LLM Post-Mortem
  async generatePostMortem(incidentId) {
    const res = await fetch(`${API_BASE}/integrations/llm/post-mortem`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ incident_id: String(incidentId) }),
    })
    return res.json()
  },

  // Slack Webhook
  async sendSlackAlert(incidentId, webhookUrl) {
    const res = await fetch(`${API_BASE}/integrations/slack/webhook`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        incident_id: String(incidentId),
        webhook_url: webhookUrl ? webhookUrl.trim() : undefined,
      }),
    })
    return res.json()
  },

  // Principal SRE Feature 1: 5% Canary Safety Circuit-Breaker Execution
  async executeCanaryRunbook(incidentId = 'inc-default', targetService = 'payment-service', rootCauseType = 'db_pool_exhaustion', canaryPercent = 5) {
    const params = new URLSearchParams({
      target_service: targetService,
      root_cause_type: rootCauseType,
      canary_percent: String(canaryPercent),
    })
    const res = await fetch(`${API_BASE}/runbook/${incidentId}/execute-canary?${params.toString()}`, {
      method: 'POST',
    })
    if (!res.ok) throw new Error('Canary execution failed')
    return res.json()
  },

  // Principal SRE Feature 2: Online Thompson Sampling Bandit Runbook Rankings
  async getBanditRankedRunbooks(rootCauseType = 'db_pool_exhaustion') {
    const res = await fetch(`${API_BASE}/runbook/${rootCauseType}/bandit-rankings`)
    if (!res.ok) throw new Error('Bandit ranking fetch failed')
    return res.json()
  },

  // Principal SRE Feature 3: OpenTelemetry Distributed Trace Critical-Path Span Attribution
  async analyzeTraceCriticalPath(rootService = 'payment-service', faultType = 'db_pool_exhaustion') {
    const params = new URLSearchParams({ root_service: rootService, fault_type: faultType })
    const res = await fetch(`${API_BASE}/chaos/trace-critical-path?${params.toString()}`, {
      method: 'POST',
    })
    if (!res.ok) throw new Error('Trace critical path failed')
    return res.json()
  },

  // Principal SRE Feature 4: Automated 4-Stage Chaos GameDay Drill
  async runChaosGameDay(scenario = 'db_pool_exhaustion', rootService = 'payment-service') {
    const res = await fetch(`${API_BASE}/chaos/gameday`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ scenario, root_service: rootService }),
    })
    if (!res.ok) throw new Error('Chaos GameDay failed')
    return res.json()
  },

  // Principal SRE Feature 5: 100-Node DAG Scalability Benchmark
  async run100NodeScalabilityBenchmark(numNodes = 100, iterations = 10) {
    const params = new URLSearchParams({ num_nodes: String(numNodes), iterations: String(iterations) })
    const res = await fetch(`${API_BASE}/eval/benchmark-100-node?${params.toString()}`, {
      method: 'POST',
    })
    if (!res.ok) throw new Error('100-node benchmark failed')
    return res.json()
  },
}

