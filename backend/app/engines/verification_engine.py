import logging
from dataclasses import dataclass
from typing import Any, Dict, Optional
import os

from app.grpc_services.diagnostic_client import DiagnosticClient

logger = logging.getLogger(__name__)


@dataclass
class CorrelatedIncident:
    incident_id: str
    suspected_service: str
    confidence_score: float
    anomaly_data: Dict[str, Any]


@dataclass
class VerifiedIncident:
    incident_id: str
    suspected_service: str
    original_confidence: float
    adjusted_confidence: float
    verification_status: str
    diagnostic_details: Dict[str, Any]


class VerificationEngine:
    def __init__(self, grpc_target: str = None):
        if not grpc_target:
            grpc_target = os.getenv("GRPC_DIAGNOSTIC_TARGET", "localhost:50051")
        self.client = DiagnosticClient(target=grpc_target)

    async def verify_incident(self, incident: Any) -> VerifiedIncident:
        """
        Takes a correlated incident, queries the suspected service via gRPC,
        and adjusts the confidence score based on actual health metrics.
        """
        suspected_svc = (
            getattr(incident, "root_cause_service_name", None)
            or getattr(incident, "suspected_service", None)
            or getattr(incident, "root_cause_service_id", "unknown")
        )
        # Normalize name like "Payment Service" -> "payment-service" if needed
        svc_lookup = str(suspected_svc).lower().replace(" ", "-")

        orig_conf = float(
            getattr(incident, "confidence", None)
            or getattr(incident, "confidence_score", 0.75)
        )
        inc_id = str(getattr(incident, "incident_id", "unknown"))

        health_data = await self.client.get_health(svc_lookup)
        if not health_data and svc_lookup != str(suspected_svc):
            health_data = await self.client.get_health(str(suspected_svc))

        adjusted_confidence = orig_conf
        verification_status = "unverified"
        diagnostic_details = {}

        if health_data is None:
            # Service is unreachable
            verification_status = "unreachable"
            diagnostic_details = {"error": "gRPC endpoint unreachable"}
        else:
            diagnostic_details = {
                "status": health_data.status,
                "active_alerts": health_data.active_alerts,
                "cpu": health_data.cpu_usage_percent,
                "memory": health_data.memory_usage_percent,
                "error_rate": health_data.error_rate,
            }

            if health_data.status in ["UNHEALTHY", "CRITICAL"]:
                # Confirmed unhealthy
                adjusted_confidence = min(0.99, orig_conf + 0.1)
                verification_status = "confirmed"
            elif health_data.status == "DEGRADED":
                # Slightly unhealthy
                adjusted_confidence = min(0.99, orig_conf + 0.05)
                verification_status = "partially_confirmed"
            elif health_data.status == "HEALTHY":
                # False positive potential
                adjusted_confidence = max(0.1, orig_conf - 0.15)
                verification_status = "refuted"

        return VerifiedIncident(
            incident_id=inc_id,
            suspected_service=str(suspected_svc),
            original_confidence=orig_conf,
            adjusted_confidence=round(adjusted_confidence, 2),
            verification_status=verification_status,
            diagnostic_details=diagnostic_details,
        )

    async def close(self):
        await self.client.close()
