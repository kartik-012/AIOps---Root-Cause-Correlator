/**
 * TypeScript definitions for gRPC Diagnostics and Health Mesh
 */

export type ServiceHealthStatus = 'HEALTHY' | 'DEGRADED' | 'UNHEALTHY' | 'CRITICAL' | 'UNREACHABLE'

export interface ServiceDiagnosticHealth {
  service_id: string
  service_name: string
  status: ServiceHealthStatus
  cpu: number
  memory: number
  error_rate: number
  p95_latency_ms: number
  active_connections: number
  active_alerts: string[]
  uptime_seconds?: number
  last_checked?: string
}

export interface ResourceMetric {
  metric_name: string
  current_value: number
  threshold: number
  unit: string
  status: 'normal' | 'warning' | 'critical'
}
