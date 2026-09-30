"""API routes for Kafka ingestion."""

from fastapi import APIRouter, HTTPException, Depends
from typing import List

from ...kafka import get_kafka_producer, KafkaProducerService, get_kafka_config
from ...kafka.events import TelemetryEvent

router = APIRouter()

def get_producer() -> KafkaProducerService:
    producer = get_kafka_producer()
    if not producer.producer:
        raise HTTPException(status_code=503, detail="Kafka producer is not available")
    return producer

@router.post("/kafka/publish-telemetry")
async def publish_telemetry(
    event: TelemetryEvent,
    producer: KafkaProducerService = Depends(get_producer)
):
    """Publish a single telemetry event to Kafka."""
    await producer.publish_telemetry(event)
    return {"status": "published", "topic": get_kafka_config().TOPIC_TELEMETRY}

@router.post("/kafka/publish-batch")
async def publish_batch(
    events: List[TelemetryEvent],
    producer: KafkaProducerService = Depends(get_producer)
):
    """Publish multiple telemetry events to Kafka."""
    for event in events:
        await producer.publish_telemetry(event)
    return {"status": "published", "count": len(events)}

@router.get("/kafka/topics")
async def get_topics():
    """Return list of configured Kafka topics."""
    return {"topics": get_kafka_config().get_all_topics()}

@router.get("/kafka/status")
async def get_status():
    """Return Kafka connection status."""
    producer = get_kafka_producer()
    return {
        "producer_connected": producer.producer is not None,
        "bootstrap_servers": get_kafka_config().BOOTSTRAP_SERVERS
    }
