import time
import asyncio
import logging
from concurrent import futures
from datetime import datetime, timezone

import grpc

# Import generated classes
from app.grpc_services.generated import diagnostics_pb2
from app.grpc_services.generated import diagnostics_pb2_grpc
from app.grpc_services.service_states import ServiceStateManager

logger = logging.getLogger(__name__)

class DiagnosticServiceServicer(diagnostics_pb2_grpc.DiagnosticServiceServicer):
    def __init__(self):
        self.state_manager = ServiceStateManager()

    def GetHealthStatus(self, request, context):
        service_id = request.service_id
        state = self.state_manager.get_state(service_id)
        
        return diagnostics_pb2.HealthResponse(
            service_id=state.service_id,
            service_name=state.service_name,
            status=state.status,
            cpu_usage_percent=state.cpu_usage_percent,
            memory_usage_percent=state.memory_usage_percent,
            disk_io_percent=state.disk_io_percent,
            active_connections=state.active_connections,
            max_connections=state.max_connections,
            error_rate=state.error_rate,
            p95_latency_ms=state.p95_latency_ms,
            uptime_seconds=state.uptime_seconds,
            last_checked=datetime.now(timezone.utc).isoformat(),
            active_alerts=state.active_alerts
        )

    def GetResourceMetrics(self, request, context):
        service_id = request.service_id
        state = self.state_manager.get_state(service_id)
        metric_types = request.metric_types if request.metric_types else ["cpu", "memory", "disk", "connections"]
        
        metrics = []
        if "cpu" in metric_types:
            metrics.append(diagnostics_pb2.ResourceMetric(
                metric_name="cpu_usage",
                current_value=state.cpu_usage_percent,
                threshold=80.0,
                unit="percent",
                status="critical" if state.cpu_usage_percent > 90.0 else ("warning" if state.cpu_usage_percent > 80.0 else "normal")
            ))
        if "memory" in metric_types:
            metrics.append(diagnostics_pb2.ResourceMetric(
                metric_name="memory_usage",
                current_value=state.memory_usage_percent,
                threshold=85.0,
                unit="percent",
                status="critical" if state.memory_usage_percent > 90.0 else ("warning" if state.memory_usage_percent > 80.0 else "normal")
            ))
        if "disk" in metric_types:
            metrics.append(diagnostics_pb2.ResourceMetric(
                metric_name="disk_io",
                current_value=state.disk_io_percent,
                threshold=80.0,
                unit="percent",
                status="critical" if state.disk_io_percent > 90.0 else ("warning" if state.disk_io_percent > 80.0 else "normal")
            ))
        if "connections" in metric_types:
            metrics.append(diagnostics_pb2.ResourceMetric(
                metric_name="active_connections",
                current_value=state.active_connections,
                threshold=state.max_connections * 0.8,
                unit="count",
                status="critical" if state.active_connections > state.max_connections * 0.9 else ("warning" if state.active_connections > state.max_connections * 0.8 else "normal")
            ))

        return diagnostics_pb2.ResourceResponse(
            service_id=service_id,
            metrics=metrics
        )

    def StreamMetrics(self, request, context):
        service_id = request.service_id
        interval = max(1, request.interval_seconds)
        
        try:
            while context.is_active():
                state = self.state_manager.get_state(service_id)
                timestamp = datetime.now(timezone.utc).isoformat()
                
                # Yield CPU
                yield diagnostics_pb2.MetricUpdate(
                    service_id=service_id,
                    metric_type="cpu",
                    value=state.cpu_usage_percent,
                    timestamp=timestamp
                )
                
                # Yield Memory
                yield diagnostics_pb2.MetricUpdate(
                    service_id=service_id,
                    metric_type="memory",
                    value=state.memory_usage_percent,
                    timestamp=timestamp
                )
                
                time.sleep(interval)
        except Exception as e:
            logger.error(f"Stream error: {e}")

import json
from http.server import HTTPServer, BaseHTTPRequestHandler
import threading

class InternalAPIHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data)
        
        path = self.path
        if path == "/internal/sim/fault":
            success = _global_state_manager.inject_fault(data.get("service_id"), data.get("fault_type"))
            self.send_response(200 if success else 404)
            self.end_headers()
            self.wfile.write(json.dumps({"success": success}).encode())
        elif path == "/internal/sim/restore":
            success = _global_state_manager.restore_health(data.get("service_id"))
            self.send_response(200 if success else 404)
            self.end_headers()
            self.wfile.write(json.dumps({"success": success}).encode())
        else:
            self.send_response(404)
            self.end_headers()

_global_state_manager = ServiceStateManager()

def run_internal_api():
    server = HTTPServer(('0.0.0.0', 8000), InternalAPIHandler)
    server.serve_forever()

def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))
    servicer = DiagnosticServiceServicer()
    servicer.state_manager = _global_state_manager
    diagnostics_pb2_grpc.add_DiagnosticServiceServicer_to_server(
        servicer, server)
    server.add_insecure_port('[::]:50051')
    
    # Start HTTP server for internal sim commands
    threading.Thread(target=run_internal_api, daemon=True).start()
    
    server.start()
    logger.info("gRPC Diagnostic Server started on port 50051")
    server.wait_for_termination()

if __name__ == '__main__':
    logging.basicConfig(level=logging.INFO)
    serve()
