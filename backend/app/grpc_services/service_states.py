import time
import random
from typing import Dict, List, Any

# Assuming these match the HealthStatus enum in protobuf
class HealthStatus:
    HEALTHY = 0
    DEGRADED = 1
    UNHEALTHY = 2
    CRITICAL = 3

class ServiceState:
    def __init__(self, service_id: str, service_name: str):
        self.service_id = service_id
        self.service_name = service_name
        self.status = HealthStatus.HEALTHY
        self.cpu_usage_percent = random.uniform(5.0, 25.0)
        self.memory_usage_percent = random.uniform(10.0, 40.0)
        self.disk_io_percent = random.uniform(1.0, 10.0)
        self.active_connections = random.randint(10, 100)
        self.max_connections = 1000
        self.error_rate = 0.0
        self.p95_latency_ms = random.uniform(5.0, 20.0)
        self.uptime_seconds = int(time.time() - random.uniform(10000, 50000))
        self.active_alerts = []
        self.last_fault = None
        self.fault_start_time = 0

    def apply_drift(self):
        # Normal fluctuation
        self.cpu_usage_percent = max(1.0, min(100.0, self.cpu_usage_percent + random.uniform(-2.0, 2.0)))
        self.memory_usage_percent = max(1.0, min(100.0, self.memory_usage_percent + random.uniform(-1.0, 1.0)))
        self.disk_io_percent = max(0.0, min(100.0, self.disk_io_percent + random.uniform(-0.5, 0.5)))
        self.active_connections = max(0, min(self.max_connections, self.active_connections + random.randint(-5, 5)))
        
        # Apply fault effects if active
        if self.last_fault == "db_pool_exhaustion":
            self.active_connections = min(self.max_connections, self.active_connections + random.randint(50, 200))
            self.p95_latency_ms += random.uniform(10.0, 50.0)
            self.error_rate = min(1.0, self.error_rate + random.uniform(0.01, 0.05))
            if self.active_connections >= self.max_connections * 0.9:
                self.status = HealthStatus.CRITICAL
                if "High Database Connections" not in self.active_alerts:
                    self.active_alerts.append("High Database Connections")
            else:
                self.status = HealthStatus.DEGRADED
                
        elif self.last_fault == "memory_leak":
            self.memory_usage_percent = min(100.0, self.memory_usage_percent + random.uniform(1.0, 5.0))
            if self.memory_usage_percent > 90.0:
                self.status = HealthStatus.CRITICAL
                self.error_rate = min(1.0, self.error_rate + random.uniform(0.0, 0.1))
                if "OOM Warning" not in self.active_alerts:
                    self.active_alerts.append("OOM Warning")
            elif self.memory_usage_percent > 70.0:
                self.status = HealthStatus.DEGRADED

        elif self.last_fault == "cpu_spike":
            self.cpu_usage_percent = min(100.0, self.cpu_usage_percent + random.uniform(10.0, 30.0))
            self.p95_latency_ms += random.uniform(5.0, 20.0)
            if self.cpu_usage_percent > 95.0:
                self.status = HealthStatus.CRITICAL
                if "CPU Starvation" not in self.active_alerts:
                    self.active_alerts.append("CPU Starvation")
            elif self.cpu_usage_percent > 80.0:
                self.status = HealthStatus.DEGRADED

        elif self.last_fault == "network_latency":
            self.p95_latency_ms += random.uniform(100.0, 500.0)
            self.error_rate = min(1.0, self.error_rate + random.uniform(0.05, 0.15))
            self.status = HealthStatus.UNHEALTHY
            if "High Network Latency" not in self.active_alerts:
                self.active_alerts.append("High Network Latency")

        elif self.last_fault == "disk_io_saturation":
            self.disk_io_percent = min(100.0, self.disk_io_percent + random.uniform(10.0, 20.0))
            if self.disk_io_percent > 95.0:
                self.status = HealthStatus.CRITICAL
                self.p95_latency_ms += random.uniform(50.0, 200.0)
                if "Disk IO Bottleneck" not in self.active_alerts:
                    self.active_alerts.append("Disk IO Bottleneck")
            elif self.disk_io_percent > 80.0:
                self.status = HealthStatus.DEGRADED

        # Decay latency and error rate if healthy
        if not self.last_fault:
            self.p95_latency_ms = max(5.0, self.p95_latency_ms - random.uniform(1.0, 5.0))
            self.error_rate = max(0.0, self.error_rate - random.uniform(0.01, 0.05))
            self.status = HealthStatus.HEALTHY
            self.active_alerts = []

class ServiceStateManager:
    def __init__(self):
        self.services: Dict[str, ServiceState] = {}
        self._initialize_services()

    @staticmethod
    def _normalize_id(service_id: str) -> str:
        """Normalize arbitrary service identifier strings into standard lowercase hyphenated slug format."""
        return (service_id or "").strip().lower().replace(" ", "-")

    def _initialize_services(self):
        service_names = [
            "api-gateway", "auth-service", "product-catalog",
            "inventory-service", "order-service", "payment-service",
            "notification-service", "shipping-service"
        ]
        for name in service_names:
            self.services[name] = ServiceState(name, name.replace("-", " ").title())

    def _get_or_create(self, service_id: str) -> ServiceState:
        norm = self._normalize_id(service_id)
        if norm not in self.services:
            self.services[norm] = ServiceState(norm, norm.replace("-", " ").title())
        return self.services[norm]

    def inject_fault(self, service_id: str, fault_type: str) -> bool:
        if not service_id:
            return False
        service = self._get_or_create(service_id)
        # Normalize common root_cause_type aliases to fault_type
        alias_map = {
            "db_connection_exhaustion": "db_pool_exhaustion",
            "network_latency_injection": "network_latency",
        }
        eff_fault = alias_map.get(fault_type, fault_type)
        service.last_fault = eff_fault
        service.fault_start_time = time.time()

        # Immediately reflect fault state before next drift tick
        if eff_fault == "db_pool_exhaustion":
            service.active_connections = int(service.max_connections * 0.96)
            service.p95_latency_ms = max(service.p95_latency_ms, 420.0)
            service.error_rate = max(service.error_rate, 0.18)
            service.status = HealthStatus.CRITICAL
            if "High Database Connections" not in service.active_alerts:
                service.active_alerts.append("High Database Connections")
        elif eff_fault == "memory_leak":
            service.memory_usage_percent = max(service.memory_usage_percent, 94.0)
            service.error_rate = max(service.error_rate, 0.12)
            service.status = HealthStatus.CRITICAL
            if "OOM Warning" not in service.active_alerts:
                service.active_alerts.append("OOM Warning")
        elif eff_fault == "cpu_spike":
            service.cpu_usage_percent = max(service.cpu_usage_percent, 97.0)
            service.p95_latency_ms = max(service.p95_latency_ms, 280.0)
            service.status = HealthStatus.CRITICAL
            if "CPU Starvation" not in service.active_alerts:
                service.active_alerts.append("CPU Starvation")
        elif eff_fault == "network_latency":
            service.p95_latency_ms = max(service.p95_latency_ms, 650.0)
            service.error_rate = max(service.error_rate, 0.15)
            service.status = HealthStatus.UNHEALTHY
            if "High Network Latency" not in service.active_alerts:
                service.active_alerts.append("High Network Latency")
        elif eff_fault == "disk_io_saturation":
            service.disk_io_percent = max(service.disk_io_percent, 96.0)
            service.p95_latency_ms = max(service.p95_latency_ms, 390.0)
            service.status = HealthStatus.CRITICAL
            if "Disk IO Bottleneck" not in service.active_alerts:
                service.active_alerts.append("Disk IO Bottleneck")
        else:
            service.status = HealthStatus.DEGRADED
            service.error_rate = max(service.error_rate, 0.10)

        return True

    def restore_health(self, service_id: str, max_connections: int | None = None) -> bool:
        """Closed-loop remediation: clear active fault and restore healthy baseline metrics."""
        if not service_id:
            return False
        service = self._get_or_create(service_id)
        service.last_fault = None
        service.fault_start_time = 0
        if max_connections is not None and max_connections > 0:
            service.max_connections = int(max_connections)
        service.status = HealthStatus.HEALTHY
        service.cpu_usage_percent = 14.5
        service.memory_usage_percent = 28.0
        service.disk_io_percent = 4.5
        service.active_connections = 32
        service.error_rate = 0.0
        service.p95_latency_ms = 11.5
        service.active_alerts = []
        return True

    def get_state(self, service_id: str, apply_drift: bool = True) -> ServiceState:
        service = self._get_or_create(service_id or "unknown-service")
        if apply_drift:
            service.apply_drift()
        return service

