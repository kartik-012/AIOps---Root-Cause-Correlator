"""Configurable dummy microservice simulator with Prometheus metric export and fault injection."""

import os
import time
import random
import asyncio
from fastapi import FastAPI, Response
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

SERVICE_NAME = os.getenv("SERVICE_NAME", "dummy-service")
DEPENDENCIES = os.getenv("DEPENDENCIES", "").split(",")
INJECT_LATENCY_MS = float(os.getenv("INJECT_LATENCY_MS", "0"))
INJECT_ERROR_RATE = float(os.getenv("INJECT_ERROR_RATE", "0"))

app = FastAPI(title=SERVICE_NAME)

# Prometheus Metrics
REQUEST_COUNT = Counter("http_requests_total", "Total HTTP requests", ["service", "endpoint", "status"])
REQUEST_LATENCY = Histogram("http_request_duration_seconds", "HTTP request latency in seconds", ["service", "endpoint"])
ACTIVE_CONNECTIONS = Gauge("service_active_connections", "Active connection pool utilization", ["service"])
CPU_USAGE = Gauge("service_cpu_utilization_percent", "Simulated CPU usage percentage", ["service"])


@app.get("/health")
def health():
    return {"status": "healthy", "service": SERVICE_NAME}


@app.get("/api/process")
async def process_request():
    start_time = time.time()
    
    # 1. Fault injection: Latency
    base_latency = random.uniform(0.01, 0.05)
    if INJECT_LATENCY_MS > 0:
        base_latency += (INJECT_LATENCY_MS / 1000.0)
    await asyncio.sleep(base_latency)

    # 2. Fault injection: Error rate
    is_error = random.random() < INJECT_ERROR_RATE
    status_code = 500 if is_error else 200

    duration = time.time() - start_time
    REQUEST_LATENCY.labels(service=SERVICE_NAME, endpoint="/api/process").observe(duration)
    REQUEST_COUNT.labels(service=SERVICE_NAME, endpoint="/api/process", status=str(status_code)).inc()

    # Update gauges
    ACTIVE_CONNECTIONS.labels(service=SERVICE_NAME).set(random.randint(15, 85))
    CPU_USAGE.labels(service=SERVICE_NAME).set(random.uniform(20.0, 75.0))

    if is_error:
        return Response(content=f"{SERVICE_NAME} internal failure", status_code=500)

    return {
        "service": SERVICE_NAME,
        "latency_ms": round(duration * 1000, 2),
        "status": "success",
    }


@app.get("/metrics")
def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", "8080"))
    uvicorn.run(app, host="0.0.0.0", port=port)
