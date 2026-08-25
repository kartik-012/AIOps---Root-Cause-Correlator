"""Detection engine router — Metric ingestion, real-time EWMA scoring, and anomaly listing."""

from datetime import datetime, timezone
import uuid
from fastapi import APIRouter, Query
from sqlalchemy import select

from app.dependencies import DBSession
from app.engines.detection_engine import DetectionEngine
from app.models.db_models import Anomaly, MetricRaw, Service
from app.models.schemas import MetricIngest, MetricIngestResponse, AnomalyOut
from app.api.v1.ws import broadcast_event

router = APIRouter()

# Global singleton DetectionEngine instance
_detection_engine = DetectionEngine(alpha=0.3, base_threshold=2.5, min_samples=3)


def get_detection_engine() -> DetectionEngine:
    return _detection_engine


@router.post("/detection/ingest", response_model=MetricIngestResponse)
async def ingest_metric(payload: MetricIngest, db: DBSession):
    """Ingest a raw telemetry data point, update EWMA baseline, and detect anomalies."""
    ts = payload.recorded_at or datetime.now(timezone.utc)

    # 1. Record raw metric in DB
    raw = MetricRaw(
        service_id=payload.service_id,
        metric_type=payload.metric_type,
        value=payload.value,
        recorded_at=ts,
    )
    db.add(raw)

    # 2. Process through detection engine
    engine = get_detection_engine()
    res = engine.process_metric(
        service_id=str(payload.service_id),
        metric_type=payload.metric_type,
        value=payload.value,
        timestamp=ts,
    )

    anomaly_id = None
    if res.is_anomaly:
        anomaly = Anomaly(
            service_id=payload.service_id,
            metric_type=payload.metric_type,
            z_score=res.z_score,
            severity=res.severity,
            detected_at=ts,
        )
        db.add(anomaly)
        db.commit()
        db.refresh(anomaly)
        anomaly_id = anomaly.id

        # Lookup service name for WebSocket notification
        svc = db.scalar(select(Service).where(Service.id == payload.service_id))
        sname = svc.name if svc else str(payload.service_id)

        # Broadcast live WebSocket event
        await broadcast_event({
            "type": "anomaly_detected",
            "service_id": str(payload.service_id),
            "service_name": sname,
            "metric_type": payload.metric_type,
            "value": payload.value,
            "z_score": res.z_score,
            "severity": res.severity,
            "timestamp": ts.isoformat(),
        })
    else:
        db.commit()

    return MetricIngestResponse(
        status="recorded",
        anomaly_detected=res.is_anomaly,
        anomaly_id=anomaly_id,
        z_score=res.z_score,
        severity=res.severity if res.is_anomaly else None,
    )


@router.get("/detection/anomalies", response_model=list[AnomalyOut])
def get_anomalies(
    db: DBSession,
    since: datetime | None = Query(None, description="Filter anomalies detected after this ISO timestamp"),
    limit: int = Query(50, ge=1, le=500),
):
    """List recent anomaly events."""
    stmt = select(Anomaly).order_by(Anomaly.detected_at.desc()).limit(limit)
    if since:
        stmt = stmt.where(Anomaly.detected_at >= since)
    anomalies = db.scalars(stmt).all()
    return anomalies


@router.get("/detection/metrics/live")
def get_live_metrics(
    service_id: str = Query("payment", description="Service name or UUID to stream"),
    metric_type: str = Query("connection_pool", description="Metric type to stream"),
):
    """Return synthetic rolling telemetry series with EWMA baseline for real-time charting."""
    import math
    import random

    now = datetime.now(timezone.utc)
    points = []
    engine = get_detection_engine()

    # Generate 20 historical points leading to present
    for i in range(20, 0, -1):
        t = now - timedelta(seconds=i * 5)
        # Base nominal with small jitter
        val = 25.0 + 3.0 * math.sin(i * 0.5) + random.uniform(-1.5, 1.5)
        res = engine.process_metric(service_id, metric_type, val, t)
        points.append({
            "timestamp": t.strftime("%H:%M:%S"),
            "value": round(val, 2),
            "ewma_mean": round(res.ewma_mean, 2),
            "upper_bound": round(res.ewma_mean + 2.5 * res.ewma_std, 2),
            "is_anomaly": res.is_anomaly,
        })

    return {"service": service_id, "metric_type": metric_type, "points": points}
