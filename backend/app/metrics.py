"""Prometheus metrics exporter for AIOps Root Cause Correlator.

Exposes production SRE observability metrics matching industry RED/USE standards:
- aiops_anomalies_detected_total (Counter)
- aiops_correlation_duration_seconds (Histogram)
- aiops_kafka_events_processed_total (Counter)
- aiops_grpc_diagnostic_calls_total (Counter)
- aiops_active_incidents (Gauge)
"""

from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST
from fastapi import Response

# 1. Anomaly detection counters
ANOMALIES_DETECTED_TOTAL = Counter(
    "aiops_anomalies_detected_total",
    "Total microservice anomaly events detected by EWMA algorithm",
    ["service_id", "metric_type", "severity"],
)

# 2. Correlation pipeline latency histogram
CORRELATION_DURATION_SECONDS = Histogram(
    "aiops_correlation_duration_seconds",
    "Time taken to isolate causal root cause across topology",
    buckets=[0.05, 0.1, 0.25, 0.5, 0.75, 1.0, 2.0, 5.0],
)

# 3. Kafka event bus counters
KAFKA_EVENTS_PROCESSED_TOTAL = Counter(
    "aiops_kafka_events_processed_total",
    "Total messages ingested and emitted across Kafka event topics",
    ["topic", "status"],
)

# 4. gRPC verification call metrics
GRPC_DIAGNOSTIC_CALLS_TOTAL = Counter(
    "aiops_grpc_diagnostic_calls_total",
    "gRPC health and resource verification calls to microservices",
    ["service_id", "status"],
)

# 5. Incident state gauge
ACTIVE_INCIDENTS_GAUGE = Gauge(
    "aiops_active_incidents",
    "Number of currently open/unresolved correlated incidents",
)


def get_metrics_response() -> Response:
    """Generate Prometheus scrape format response."""
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)
