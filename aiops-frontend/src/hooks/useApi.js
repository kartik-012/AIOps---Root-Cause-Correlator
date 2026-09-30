const API_BASE = '/api/v1'

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
    const res = await fetch('/graphql', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ query, variables }),
    })
    return res.json()
  },
}
