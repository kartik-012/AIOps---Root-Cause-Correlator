# 📘 api-spec.md

**REST + WebSocket API — AIOps Root Cause Correlator**
**Base path:** `/api/v1`

---

## 1. Services & Dependency Graph

### `GET /services`
Returns all registered services and their revenue weight.
```json
[
  { "id": "uuid", "name": "payment-service", "revenue_weight": 10.0 }
]
```

### `GET /services/graph`
Returns the full dependency graph.
```json
{
  "nodes": [{ "id": "uuid", "name": "api-gateway" }],
  "edges": [{ "from": "uuid-gateway", "to": "uuid-order" }]
}
```

---

## 2. Detection Engine

### `POST /detection/ingest`
Ingest a raw metric point (called by the simulator or a Prometheus scrape adapter).
```json
// Request
{
  "service_id": "uuid",
  "metric_type": "latency_ms",
  "value": 342.5,
  "recorded_at": "2026-08-25T10:00:05Z"
}
```
```json
// Response
{ "status": "recorded", "anomaly_detected": true, "anomaly_id": "uuid", "z_score": 4.2 }
```

### `GET /detection/anomalies?since=<timestamp>`
Returns recent anomaly events, unclustered.

---

## 3. Correlation Engine

### `POST /correlation/run`
Triggers correlation on current unclustered anomalies. Returns one or more incidents (multi-root-cause support).
```json
// Response
{
  "incidents": [
    {
      "incident_id": "uuid",
      "root_cause_service": "payment-service",
      "confidence": 0.87,
      "affected_services": ["order-service", "api-gateway"],
      "is_multi_root_cause": false
    }
  ]
}
```

### `GET /correlation/incidents/{incident_id}`
Full incident detail: timeline, affected services in propagation order, anomaly signature.

---

## 4. Suppression Engine

### `POST /suppression/check`
Checks a new anomaly signature against known false-positive patterns before full correlation runs.
```json
// Request
{ "anomaly_signature": [0.2, 3, "payment-service-id", "latency", 4.1, 2, 45] }
```
```json
// Response
{ "suppress": true, "matched_incident_id": "uuid", "similarity": 0.94 }
```

### `POST /suppression/mark-false-positive/{incident_id}`
Human reviewer marks a past incident as benign — feeds future suppression.

---

## 5. Prediction Engine (Blast Radius)

### `GET /prediction/blast-radius/{incident_id}`
```json
// Response
{
  "predictions": [
    { "service": "api-gateway", "eta_seconds": 40, "confidence": 0.72 },
    { "service": "notification-service", "eta_seconds": 65, "confidence": 0.55 }
  ]
}
```

---

## 6. Counterfactual Engine

### `POST /counterfactual/simulate`
```json
// Request
{
  "incident_id": "uuid",
  "modified_parameter": { "service": "payment-service", "metric": "latency_ms", "capped_at": 200 }
}
```
```json
// Response
{
  "would_cascade": false,
  "original_affected_services": ["order-service", "api-gateway"],
  "simulated_affected_services": []
}
```

---

## 7. Impact & Runbook

### `GET /impact/{incident_id}`
```json
{ "impact_score": 8.4, "severity": "high", "revenue_weighted": true }
```

### `GET /runbook/{root_cause_type}`
```json
{ "suggested_action": "Scale connection pool, check for connection leaks in payment service" }
```

### `POST /runbook/{incident_id}/approve`
Human-in-the-loop approval — required before any suggested action is marked actionable. No auto-execution endpoint exists, by design (`rules.md` Section 5).

---

## 8. Explanation Layer (LLM)

### `POST /explain/{incident_id}`
```json
// Response
{
  "summary": "Root cause identified as connection pool exhaustion in payment-service, cascading to order-service and api-gateway. Two similar past incidents support this hypothesis.",
  "evidence": ["metric_anomaly", "trace_latency", "recent_deployment", "historical_similarity"]
}
```

---

## 9. WebSocket — Live Incident Stream

### `WS /ws/incidents`
Pushes real-time events as they occur:
```json
{ "type": "anomaly_detected", "service": "payment-service", "z_score": 4.2, "timestamp": "..." }
{ "type": "incident_correlated", "incident_id": "uuid", "root_cause": "payment-service" }
{ "type": "blast_radius_updated", "incident_id": "uuid", "predictions": [...] }
```

Frontend subscribes once on dashboard load; used to drive the live dependency graph and timeline without polling.

---

## 10. Evaluation Endpoint (internal / dev only)

### `POST /eval/run-scenarios`
Runs the full injected-scenario test suite (see `evaluation-scenarios.md`) and returns computed metrics.
```json
{
  "top1_accuracy": 0.82,
  "top3_accuracy": 0.93,
  "multi_incident_separation_accuracy": 0.75,
  "suppression_precision": 0.91,
  "suppression_recall": 0.85,
  "mean_detection_time_seconds": 4.7
}
```

This endpoint is what generates the actual numbers for your resume/README — not a manual claim.
