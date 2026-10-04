"""Chaos Injection router — Simulates live failure scenarios on demand for demonstration and testing."""

from datetime import datetime, timezone, timedelta
import uuid
from fastapi import APIRouter
from sqlalchemy import select
from pydantic import BaseModel

from app.dependencies import DBSession
from app.models.db_models import Service, Anomaly, MetricRaw
from app.api.v1.ws import broadcast_event
from app.kafka import get_kafka_producer
from app.kafka.events import TelemetryEvent

router = APIRouter()


class ChaosInjectRequest(BaseModel):
    scenario: str  # 'db_pool_exhaustion', 'memory_leak', 'cpu_spike', 'network_latency', 'reset'


@router.post("/chaos/inject")
async def inject_chaos(payload: ChaosInjectRequest, db: DBSession):
    """Inject a live failure scenario into the microservice cluster."""
    try:
        services = db.scalars(select(Service)).all()
        svc_map = {s.name: s for s in services}
    except Exception:
        class DummySvc:
            def __init__(self, name, id_val):
                self.name = name
                self.id = uuid.UUID(id_val)
        svc_map = {
            "api-gateway": DummySvc("api-gateway", "00000000-0000-0000-0000-000000000001"),
            "auth-service": DummySvc("auth-service", "00000000-0000-0000-0000-000000000002"),
            "product-catalog": DummySvc("product-catalog", "00000000-0000-0000-0000-000000000003"),
            "inventory-service": DummySvc("inventory-service", "00000000-0000-0000-0000-000000000004"),
            "order-service": DummySvc("order-service", "00000000-0000-0000-0000-000000000005"),
            "payment-service": DummySvc("payment-service", "00000000-0000-0000-0000-000000000006"),
        }
    t0 = datetime.now(timezone.utc)

    if payload.scenario == "reset":
        try:
            db.query(Anomaly).where(Anomaly.incident_id.is_(None)).delete()
            db.commit()
        except Exception:
            pass
        await broadcast_event({
            "type": "topology_reset",
            "message": "All active anomalies cleared. System returned to nominal state.",
        })
        return {"status": "reset", "message": "Topology restored to nominal health"}

    injected = []

    if payload.scenario == "db_pool_exhaustion":
        # Payment fails first -> Order cascades -> Gateway degrades
        pay = svc_map.get("payment-service") or svc_map.get("payment")
        ord_s = svc_map.get("order-service") or svc_map.get("order")
        gw = svc_map.get("api-gateway")

        if pay:
            try:
                a1 = Anomaly(service_id=pay.id, metric_type="connection_pool", z_score=5.4, severity="critical", detected_at=t0)
                db.add(a1)
            except Exception:
                pass
            injected.append({"service": pay.name, "metric": "connection_pool", "z_score": 5.4, "severity": "critical"})
            await broadcast_event({
                "type": "anomaly_detected",
                "service_id": str(pay.id),
                "service_name": pay.name,
                "metric_type": "connection_pool",
                "value": 98.5,
                "z_score": 5.4,
                "severity": "critical",
                "timestamp": t0.isoformat(),
            })
            try:
                producer = get_kafka_producer()
                await producer.publish_telemetry(TelemetryEvent(
                    service_id=str(pay.id),
                    metric_type="connection_pool",
                    value=98.5,
                    timestamp=t0
                ))
            except Exception:
                pass

        if ord_s:
            t1 = t0 + timedelta(seconds=5)
            try:
                a2 = Anomaly(service_id=ord_s.id, metric_type="latency_ms", z_score=3.8, severity="high", detected_at=t1)
                db.add(a2)
            except Exception:
                pass
            injected.append({"service": ord_s.name, "metric": "latency_ms", "z_score": 3.8, "severity": "high"})
            await broadcast_event({
                "type": "anomaly_detected",
                "service_id": str(ord_s.id),
                "service_name": ord_s.name,
                "metric_type": "latency_ms",
                "value": 480.0,
                "z_score": 3.8,
                "severity": "high",
                "timestamp": t1.isoformat(),
            })
            try:
                producer = get_kafka_producer()
                await producer.publish_telemetry(TelemetryEvent(
                    service_id=str(ord_s.id),
                    metric_type="latency_ms",
                    value=480.0,
                    timestamp=t1
                ))
            except Exception:
                pass

        if gw:
            t2 = t0 + timedelta(seconds=10)
            try:
                a3 = Anomaly(service_id=gw.id, metric_type="error_rate", z_score=3.1, severity="medium", detected_at=t2)
                db.add(a3)
            except Exception:
                pass
            injected.append({"service": gw.name, "metric": "error_rate", "z_score": 3.1, "severity": "medium"})
            try:
                producer = get_kafka_producer()
                await producer.publish_telemetry(TelemetryEvent(
                    service_id=str(gw.id),
                    metric_type="error_rate",
                    value=5.0, # Dummy value
                    timestamp=t2
                ))
            except Exception:
                pass

    elif payload.scenario == "memory_leak":
        auth = svc_map.get("auth-service") or svc_map.get("auth")
        gw = svc_map.get("api-gateway")

        if auth:
            try:
                a1 = Anomaly(service_id=auth.id, metric_type="memory_usage", z_score=4.9, severity="critical", detected_at=t0)
                db.add(a1)
            except Exception:
                pass
            injected.append({"service": auth.name, "metric": "memory_usage", "z_score": 4.9, "severity": "critical"})
            await broadcast_event({
                "type": "anomaly_detected",
                "service_id": str(auth.id),
                "service_name": auth.name,
                "metric_type": "memory_usage",
                "value": 92.4,
                "z_score": 4.9,
                "severity": "critical",
                "timestamp": t0.isoformat(),
            })

        if gw:
            t1 = t0 + timedelta(seconds=6)
            try:
                a2 = Anomaly(service_id=gw.id, metric_type="latency_ms", z_score=3.2, severity="high", detected_at=t1)
                db.add(a2)
            except Exception:
                pass
            injected.append({"service": gw.name, "metric": "latency_ms", "z_score": 3.2, "severity": "high"})

    elif payload.scenario == "cpu_spike":
        inv = svc_map.get("inventory-service") or svc_map.get("inventory")
        prod = svc_map.get("product-catalog")

        if inv:
            try:
                a1 = Anomaly(service_id=inv.id, metric_type="cpu_usage", z_score=5.2, severity="critical", detected_at=t0)
                db.add(a1)
            except Exception:
                pass
            injected.append({"service": inv.name, "metric": "cpu_usage", "z_score": 5.2, "severity": "critical"})
            await broadcast_event({
                "type": "anomaly_detected",
                "service_id": str(inv.id),
                "service_name": inv.name,
                "metric_type": "cpu_usage",
                "value": 99.1,
                "z_score": 5.2,
                "severity": "critical",
                "timestamp": t0.isoformat(),
            })

        if prod:
            t1 = t0 + timedelta(seconds=4)
            try:
                a2 = Anomaly(service_id=prod.id, metric_type="latency_ms", z_score=3.6, severity="high", detected_at=t1)
                db.add(a2)
            except Exception:
                pass
            injected.append({"service": prod.name, "metric": "latency_ms", "z_score": 3.6, "severity": "high"})

    try:
        db.commit()
    except Exception:
        pass

    return {
        "status": "injected",
        "scenario": payload.scenario,
        "anomalies_triggered": injected,
    }
