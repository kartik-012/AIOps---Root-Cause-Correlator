import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

from app.grpc_services.service_states import ServiceStateManager, HealthStatus
from app.engines.verification_engine import VerificationEngine, CorrelatedIncident
from app.grpc_services.diagnostic_client import HealthData

def test_service_state_manager_drift():
    manager = ServiceStateManager()
    state = manager.get_state("api-gateway")
    
    assert state.service_id == "api-gateway"
    assert state.status == HealthStatus.HEALTHY
    
    initial_cpu = state.cpu_usage_percent
    manager.get_state("api-gateway")
    # Drift happens
    assert state.cpu_usage_percent != initial_cpu

def test_fault_injection_and_restoration():
    manager = ServiceStateManager()
    assert manager.inject_fault("api-gateway", "cpu_spike") is True
    
    state = manager.get_state("api-gateway")
    assert state.last_fault == "cpu_spike"
    
    # Applying drift many times should make it critical or degraded
    for _ in range(10):
        manager.get_state("api-gateway")
        
    state = manager.get_state("api-gateway")
    assert state.cpu_usage_percent > 80.0
    
    assert manager.restore_health("api-gateway") is True
    state = manager.get_state("api-gateway")
    assert state.last_fault is None

@pytest.mark.asyncio
async def test_verification_engine_unhealthy():
    engine = VerificationEngine(grpc_target="dummy")
    engine.client = AsyncMock()
    
    # Mocking unhealthy service
    mock_health = HealthData(
        service_id="api-gateway",
        service_name="API Gateway",
        status="UNHEALTHY",
        cpu_usage_percent=95.0,
        memory_usage_percent=50.0,
        disk_io_percent=10.0,
        active_connections=100,
        max_connections=1000,
        error_rate=0.1,
        p95_latency_ms=200.0,
        uptime_seconds=1000,
        last_checked="now",
        active_alerts=["High Latency"]
    )
    engine.client.get_health.return_value = mock_health
    
    incident = CorrelatedIncident(
        incident_id="inc-1",
        suspected_service="api-gateway",
        confidence_score=0.8,
        anomaly_data={}
    )
    
    result = await engine.verify_incident(incident)
    
    assert result.verification_status == "confirmed"
    assert result.adjusted_confidence == 0.9  # 0.8 + 0.1
    assert result.diagnostic_details["status"] == "UNHEALTHY"

@pytest.mark.asyncio
async def test_verification_engine_healthy():
    engine = VerificationEngine(grpc_target="dummy")
    engine.client = AsyncMock()
    
    # Mocking healthy service
    mock_health = HealthData(
        service_id="api-gateway",
        service_name="API Gateway",
        status="HEALTHY",
        cpu_usage_percent=20.0,
        memory_usage_percent=30.0,
        disk_io_percent=5.0,
        active_connections=50,
        max_connections=1000,
        error_rate=0.0,
        p95_latency_ms=15.0,
        uptime_seconds=10000,
        last_checked="now",
        active_alerts=[]
    )
    engine.client.get_health.return_value = mock_health
    
    incident = CorrelatedIncident(
        incident_id="inc-2",
        suspected_service="api-gateway",
        confidence_score=0.8,
        anomaly_data={}
    )
    
    result = await engine.verify_incident(incident)
    
    assert result.verification_status == "refuted"
    assert result.adjusted_confidence == 0.65  # 0.8 - 0.15
    assert result.diagnostic_details["status"] == "HEALTHY"

@pytest.mark.asyncio
async def test_verification_engine_unreachable():
    engine = VerificationEngine(grpc_target="dummy")
    engine.client = AsyncMock()
    engine.client.get_health.return_value = None
    
    incident = CorrelatedIncident(
        incident_id="inc-3",
        suspected_service="api-gateway",
        confidence_score=0.7,
        anomaly_data={}
    )
    
    result = await engine.verify_incident(incident)
    
    assert result.verification_status == "unreachable"
    assert result.adjusted_confidence == 0.7  # unchanged
    assert "error" in result.diagnostic_details
