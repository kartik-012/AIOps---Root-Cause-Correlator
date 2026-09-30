/**
 * TypeScript definitions for Apache Kafka Event Bus Topics
 */

export interface TelemetryEvent {
  service_id: string
  metric_type: string
  value: number
  timestamp?: string
  trace_id?: string
}

export interface IncidentEvent {
  incident_id: string
  root_cause_service: string
  severity: string
  confidence: number
  affected_services?: string[]
  event_type: 'detected' | 'updated' | 'resolved'
  timestamp?: string
}

export interface RemediationEvent {
  incident_id: string
  action: string
  status: 'requested' | 'approved' | 'executed' | 'completed' | 'rejected'
  approved_by?: string
  timestamp?: string
}

export interface AuditEvent {
  event_type: string
  actor: string
  details: Record<string, unknown>
  timestamp?: string
}
