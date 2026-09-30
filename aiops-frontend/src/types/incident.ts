/**
 * TypeScript definitions for Incident Intelligence and RCA Engine
 */

export type SeverityLevel = 'low' | 'medium' | 'high' | 'critical'
export type IncidentStatus = 'INVESTIGATING' | 'IDENTIFIED' | 'MITIGATING' | 'RESOLVED'

export interface AffectedService {
  service_id: string
  service_name: string
  propagation_order: number
  affected_at: string
  latency_ms?: number
  error_rate?: number
}

export interface AnomalyRecord {
  id: string
  service_id: string
  metric_type: string
  value: number
  z_score: number
  severity: SeverityLevel
  detected_at: string
}

export interface RootCauseHypothesis {
  service: string
  component: string
  confidence: number
  verification_status: 'CONFIRMED' | 'PARTIALLY_CONFIRMED' | 'REFUTED' | 'UNREACHABLE' | 'UNVERIFIED'
  details?: Record<string, unknown>
}

export interface CorrelatedIncident {
  id: string
  incident_id?: string
  root_cause_service: string
  root_cause_service_name?: string
  root_cause_type: string
  confidence: number
  confidence_at_detection?: number
  is_multi_root_cause: boolean
  affected_services: (string | AffectedService)[]
  anomalies?: AnomalyRecord[]
  timestamp_start: string
  timestamp_end?: string | null
  status?: IncidentStatus
  signature?: number[]
}
