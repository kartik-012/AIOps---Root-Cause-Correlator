import logging
import asyncio
from typing import List, Dict, Any, AsyncGenerator, Optional
from dataclasses import dataclass
import grpc

from app.grpc_services.generated import diagnostics_pb2
from app.grpc_services.generated import diagnostics_pb2_grpc

logger = logging.getLogger(__name__)

@dataclass
class HealthData:
    service_id: str
    service_name: str
    status: str
    cpu_usage_percent: float
    memory_usage_percent: float
    disk_io_percent: float
    active_connections: int
    max_connections: int
    error_rate: float
    p95_latency_ms: float
    uptime_seconds: int
    last_checked: str
    active_alerts: List[str]

@dataclass
class ResourceMetric:
    metric_name: str
    current_value: float
    threshold: float
    unit: str
    status: str

@dataclass
class MetricUpdate:
    service_id: str
    metric_type: str
    value: float
    timestamp: str

class DiagnosticClient:
    def __init__(self, target: str = "localhost:50051"):
        self.target = target
        self._channel = None
        self._stub = None

    async def connect(self):
        if not self._channel:
            self._channel = grpc.aio.insecure_channel(self.target)
            self._stub = diagnostics_pb2_grpc.DiagnosticServiceStub(self._channel)

    async def close(self):
        if self._channel:
            await self._channel.close()
            self._channel = None
            self._stub = None

    async def get_health(self, service_id: str, timeout: float = 5.0) -> Optional[HealthData]:
        await self.connect()
        try:
            req = diagnostics_pb2.HealthRequest(service_id=service_id)
            resp = await self._stub.GetHealthStatus(req, timeout=timeout)
            
            # Map enum to string
            status_map = {0: "HEALTHY", 1: "DEGRADED", 2: "UNHEALTHY", 3: "CRITICAL"}
            status_str = status_map.get(resp.status, "UNKNOWN")
            
            return HealthData(
                service_id=resp.service_id,
                service_name=resp.service_name,
                status=status_str,
                cpu_usage_percent=resp.cpu_usage_percent,
                memory_usage_percent=resp.memory_usage_percent,
                disk_io_percent=resp.disk_io_percent,
                active_connections=resp.active_connections,
                max_connections=resp.max_connections,
                error_rate=resp.error_rate,
                p95_latency_ms=resp.p95_latency_ms,
                uptime_seconds=resp.uptime_seconds,
                last_checked=resp.last_checked,
                active_alerts=list(resp.active_alerts)
            )
        except grpc.aio.AioRpcError as e:
            logger.error(f"gRPC call failed: {e.code()} - {e.details()}")
            return None

    async def get_resources(self, service_id: str, metrics: List[str] = None, timeout: float = 5.0) -> List[ResourceMetric]:
        await self.connect()
        try:
            req = diagnostics_pb2.ResourceRequest(service_id=service_id, metric_types=metrics or [])
            resp = await self._stub.GetResourceMetrics(req, timeout=timeout)
            
            results = []
            for m in resp.metrics:
                results.append(ResourceMetric(
                    metric_name=m.metric_name,
                    current_value=m.current_value,
                    threshold=m.threshold,
                    unit=m.unit,
                    status=m.status
                ))
            return results
        except grpc.aio.AioRpcError as e:
            logger.error(f"gRPC call failed: {e.code()} - {e.details()}")
            return []

    async def stream_metrics(self, service_id: str, interval_seconds: int = 1) -> AsyncGenerator[MetricUpdate, None]:
        await self.connect()
        try:
            req = diagnostics_pb2.StreamRequest(service_id=service_id, interval_seconds=interval_seconds)
            async for update in self._stub.StreamMetrics(req):
                yield MetricUpdate(
                    service_id=update.service_id,
                    metric_type=update.metric_type,
                    value=update.value,
                    timestamp=update.timestamp
                )
        except grpc.aio.AioRpcError as e:
            logger.error(f"gRPC stream failed: {e.code()} - {e.details()}")
