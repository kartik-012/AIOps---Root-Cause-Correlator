"""Diagnostics API — gRPC-backed service health inspection and fault injection.

Queries the gRPC Diagnostic Service for real-time service health,
and exposes fault injection endpoints for the simulator.
"""

import os
from fastapi import APIRouter, HTTPException, Query
import httpx

from app.grpc_services.diagnostic_client import DiagnosticClient

GRPC_TARGET = os.getenv("GRPC_DIAGNOSTIC_TARGET", "localhost:50051")
INTERNAL_SIM_API = os.getenv("INTERNAL_SIM_API", "http://localhost:8000")

_client = DiagnosticClient(target=GRPC_TARGET)

router = APIRouter()


@router.get("/diagnostics/all")
async def get_all_services_health():
    """Query gRPC diagnostic service for health of all tracked microservices."""
    services = [
        "api-gateway", "auth-service", "product-catalog",
        "inventory-service", "order-service", "payment-service",
        "notification-service", "shipping-service",
    ]
    results = {}
    for svc in services:
        health = await _client.get_health(svc)
        if health:
            results[svc] = {
                "status": health.status,
                "cpu": round(health.cpu_usage_percent, 1),
                "memory": round(health.memory_usage_percent, 1),
                "error_rate": round(health.error_rate, 3),
                "p95_latency_ms": round(health.p95_latency_ms, 1),
                "active_connections": health.active_connections,
                "active_alerts": health.active_alerts,
            }
        else:
            results[svc] = {"status": "UNREACHABLE"}
    return {"services": results}


@router.get("/diagnostics/{service_id}/health")
async def get_service_health(service_id: str):
    """Query gRPC for a single service's health snapshot."""
    health = await _client.get_health(service_id)
    if not health:
        raise HTTPException(status_code=503, detail=f"Diagnostic service unavailable for {service_id}")
    return health


@router.get("/diagnostics/{service_id}/resources")
async def get_service_resources(
    service_id: str,
    metrics: str = Query("cpu,memory,disk,connections", description="Comma-separated metric types"),
):
    """Query gRPC for detailed resource metrics of a service."""
    metric_list = [m.strip() for m in metrics.split(",")]
    resources = await _client.get_resources(service_id, metric_list)
    if not resources:
        raise HTTPException(status_code=503, detail=f"Diagnostic service unavailable for {service_id}")
    return {"service_id": service_id, "metrics": resources}


@router.post("/diagnostics/{service_id}/inject-fault")
async def inject_fault(
    service_id: str,
    fault_type: str = Query(..., description="One of: db_pool_exhaustion, memory_leak, cpu_spike, network_latency, disk_io_saturation"),
):
    """Inject a fault into the simulated gRPC diagnostic service."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.post(
                f"{INTERNAL_SIM_API}/internal/sim/fault",
                json={"service_id": service_id, "fault_type": fault_type},
            )
            return {"status": "injected", "service_id": service_id, "fault_type": fault_type, **resp.json()}
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="gRPC diagnostic simulator not reachable")


@router.post("/diagnostics/{service_id}/restore")
async def restore_health(service_id: str):
    """Restore a simulated service to healthy state."""
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.post(
                f"{INTERNAL_SIM_API}/internal/sim/restore",
                json={"service_id": service_id},
            )
            return {"status": "restored", "service_id": service_id, **resp.json()}
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="gRPC diagnostic simulator not reachable")
