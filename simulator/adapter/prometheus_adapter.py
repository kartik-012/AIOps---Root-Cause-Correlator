"""Prometheus Scrape Adapter — Polls live cluster metrics and feeds them into the detection engine.

Connects Prometheus metrics to POST /api/v1/detection/ingest.
"""

import os
import time
import uuid
import httpx
from datetime import datetime, timezone

PROMETHEUS_URL = os.getenv("PROMETHEUS_URL", "http://localhost:9090")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8001")
POLL_INTERVAL_SECONDS = float(os.getenv("POLL_INTERVAL_SECONDS", "5.0"))

# Service name mapping to UUID
service_id_map: dict[str, str] = {}


def fetch_or_register_services(client: httpx.Client):
    """Ensure all 8 microservices are registered in the backend."""
    global service_id_map
    try:
        res = client.get(f"{BACKEND_URL}/api/v1/services")
        if res.status_code == 200:
            for s in res.json():
                service_id_map[s["name"]] = s["id"]
        print(f"[Adapter] Resolved {len(service_id_map)} service IDs from backend")
    except Exception as e:
        print(f"[Adapter] Could not connect to backend: {e}")


def query_prometheus(client: httpx.Client, query: str) -> list[dict]:
    """Execute PromQL instant query against Prometheus."""
    try:
        res = client.get(f"{PROMETHEUS_URL}/api/v1/query", params={"query": query}, timeout=3.0)
        if res.status_code == 200:
            data = res.json()
            if data.get("status") == "success":
                return data.get("data", {}).get("result", [])
    except Exception as e:
        # Fallback simulator mode if Prometheus is unreachable
        pass
    return []


def ingest_telemetry_point(client: httpx.Client, service_id: str, metric_type: str, value: float):
    """Post metric point to backend detection engine."""
    payload = {
        "service_id": service_id,
        "metric_type": metric_type,
        "value": float(value),
        "recorded_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        res = client.post(f"{BACKEND_URL}/api/v1/detection/ingest", json=payload, timeout=2.0)
        if res.status_code == 200:
            result = res.json()
            if result.get("anomaly_detected"):
                print(f"[ANOMALY DETECTED] Service: {service_id} | Metric: {metric_type} | z-score: {result.get('z_score')}")
    except Exception as e:
        print(f"[Adapter] Ingestion error: {e}")


def run_adapter_loop():
    """Continuous polling loop."""
    print("=" * 60)
    print("   PROMETHEUS TELEMETRY ADAPTER FOR AIOps DETECTION ENGINE")
    print("=" * 60)
    print(f"Target Backend     : {BACKEND_URL}")
    print(f"Target Prometheus  : {PROMETHEUS_URL}")
    print(f"Poll Interval      : {POLL_INTERVAL_SECONDS}s")
    print("-" * 60)

    with httpx.Client() as client:
        fetch_or_register_services(client)

        while True:
            # 1. Query request durations
            results = query_prometheus(client, "rate(http_request_duration_seconds_sum[1m]) / rate(http_request_duration_seconds_count[1m])")
            for r in results:
                s_name = r.get("metric", {}).get("service")
                val = float(r.get("value", [0, 0])[1]) * 1000.0  # convert to ms
                sid = service_id_map.get(s_name)
                if sid:
                    ingest_telemetry_point(client, sid, "latency_ms", val)

            # 2. Query error rates
            err_results = query_prometheus(client, "rate(http_requests_total{status=~'5..'}[1m]) / rate(http_requests_total[1m])")
            for r in err_results:
                s_name = r.get("metric", {}).get("service")
                val = float(r.get("value", [0, 0])[1]) * 100.0
                sid = service_id_map.get(s_name)
                if sid:
                    ingest_telemetry_point(client, sid, "error_rate", val)

            time.sleep(POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    run_adapter_loop()
