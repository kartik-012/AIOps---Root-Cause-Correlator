"""API routes for Kafka ingestion."""

from fastapi import APIRouter, HTTPException, Depends
from typing import List

from ...kafka import get_kafka_producer, KafkaProducerService, get_kafka_config
from ...kafka.events import TelemetryEvent

router = APIRouter()

def get_producer() -> KafkaProducerService:
    return get_kafka_producer()

@router.post("/kafka/publish-telemetry")
async def publish_telemetry(
    event: TelemetryEvent,
    producer: KafkaProducerService = Depends(get_producer)
):
    """Publish a single telemetry event to Kafka."""
    if producer.producer:
        try:
            await producer.publish_telemetry(event)
            return {"status": "published", "topic": get_kafka_config().TOPIC_TELEMETRY}
        except Exception:
            pass
    return {"status": "simulated", "topic": get_kafka_config().TOPIC_TELEMETRY, "mode": "virtual_event_bus"}

@router.post("/kafka/publish-batch")
async def publish_batch(
    events: List[TelemetryEvent],
    producer: KafkaProducerService = Depends(get_producer)
):
    """Publish multiple telemetry events to Kafka."""
    if producer.producer:
        try:
            for event in events:
                await producer.publish_telemetry(event)
            return {"status": "published", "count": len(events)}
        except Exception:
            pass
    return {"status": "simulated", "count": len(events), "mode": "virtual_event_bus"}

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
