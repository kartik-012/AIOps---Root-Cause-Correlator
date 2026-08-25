"""Chaos Injection router — Simulates live failure scenarios on demand for demonstration and testing."""

from datetime import datetime, timezone, timedelta
import uuid
from fastapi import APIRouter
from sqlalchemy import select
from pydantic import BaseModel

from app.dependencies import DBSession
from app.models.db_models import Service, Anomaly, MetricRaw
from app.api.v1.ws import broadcast_event

router = APIRouter()


class ChaosInjectRequest(BaseModel):
    scenario: str  # 'db_pool_exhaustion', 'memory_leak', 'cpu_spike', 'network_latency', 'reset'


@router.post("/chaos/inject")
async def inject_chaos(payload: ChaosInjectRequest, db: DBSession):
    """Inject a live failure scenario into the microservice cluster."""
    services = db.scalars(select(Service)).all()
    svc_map = {s.name: s for s in services}
    t0 = datetime.now(timezone.utc)

    if payload.scenario == "reset":
        # Clear active unclustered anomalies
        db.query(Anomaly).where(Anomaly.incident_id.is_(None)).delete()
        db.commit()
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
            a1 = Anomaly(service_id=pay.id, metric_type="connection_pool", z_score=5.4, severity="critical", detected_at=t0)
            db.add(a1)
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

        if ord_s:
            t1 = t0 + timedelta(seconds=5)
            a2 = Anomaly(service_id=ord_s.id, metric_type="latency_ms", z_score=3.8, severity="high", detected_at=t1)
            db.add(a2)
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

        if gw:
            t2 = t0 + timedelta(seconds=10)
            a3 = Anomaly(service_id=gw.id, metric_type="error_rate", z_score=3.1, severity="medium", detected_at=t2)
            db.add(a3)
            injected.append({"service": gw.name, "metric": "error_rate", "z_score": 3.1, "severity": "medium"})

    elif payload.scenario == "memory_leak":
        auth = svc_map.get("auth-service") or svc_map.get("auth")
        gw = svc_map.get("api-gateway")

        if auth:
            a1 = Anomaly(service_id=auth.id, metric_type="memory_usage", z_score=4.9, severity="critical", detected_at=t0)
            db.add(a1)
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
            a2 = Anomaly(service_id=gw.id, metric_type="latency_ms", z_score=3.2, severity="high", detected_at=t1)
            db.add(a2)
            injected.append({"service": gw.name, "metric": "latency_ms", "z_score": 3.2, "severity": "high"})

    elif payload.scenario == "cpu_spike":
        inv = svc_map.get("inventory-service") or svc_map.get("inventory")
        prod = svc_map.get("product-catalog")

        if inv:
            a1 = Anomaly(service_id=inv.id, metric_type="cpu_usage", z_score=5.2, severity="critical", detected_at=t0)
            db.add(a1)
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
            a2 = Anomaly(service_id=prod.id, metric_type="latency_ms", z_score=3.6, severity="high", detected_at=t1)
            db.add(a2)
            injected.append({"service": prod.name, "metric": "latency_ms", "z_score": 3.6, "severity": "high"})

    db.commit()

    return {
        "status": "injected",
        "scenario": payload.scenario,
        "anomalies_triggered": injected,
    }
