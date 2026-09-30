"""Kafka Producer Service."""

import json
import logging
from typing import Any
from aiokafka import AIOKafkaProducer
from pydantic import BaseModel

from .config import KafkaConfig, get_kafka_config
from .events import TelemetryEvent, IncidentEvent, AuditEvent, RemediationEvent

logger = logging.getLogger(__name__)

class KafkaProducerService:
    """Async Kafka producer service singleton."""
    
    _instance = None
    
    def __new__(cls, *args, **kwargs):
        if cls._instance is None:
            cls._instance = super(KafkaProducerService, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, config: KafkaConfig = None):
        if self._initialized:
            return
        self.config = config or get_kafka_config()
        self.producer = None
        self._initialized = True
        
    async def start(self):
        """Start the Kafka producer."""
        try:
            self.producer = AIOKafkaProducer(
                bootstrap_servers=self.config.BOOTSTRAP_SERVERS,
                value_serializer=lambda v: json.dumps(v, default=str).encode('utf-8')
            )
            await self.producer.start()
            logger.info(f"Kafka Producer started on {self.config.BOOTSTRAP_SERVERS}")
        except Exception as e:
            logger.error(f"Failed to start Kafka Producer: {e}")
            self.producer = None

    async def stop(self):
        """Stop the Kafka producer."""
        if self.producer:
            await self.producer.stop()
            logger.info("Kafka Producer stopped.")
            self.producer = None
            
    async def _publish(self, topic: str, event: BaseModel):
        """Internal method to publish a Pydantic model to a topic."""
        if not self.producer:
            logger.warning(f"Cannot publish to {topic}: Producer is not started or failed to initialize.")
            return
            
        try:
            await self.producer.send_and_wait(topic, event.model_dump())
            logger.debug(f"Published event to {topic}")
        except Exception as e:
            logger.error(f"Error publishing event to {topic}: {e}")

    async def publish_telemetry(self, event: TelemetryEvent):
        await self._publish(self.config.TOPIC_TELEMETRY, event)

    async def publish_incident(self, event: IncidentEvent):
        topic = self.config.TOPIC_INCIDENT_DETECTED if event.event_type == "detected" else self.config.TOPIC_INCIDENT_UPDATED
        await self._publish(topic, event)
        
    async def publish_remediation(self, event: RemediationEvent):
        topic = self.config.TOPIC_REMEDIATION_COMPLETED if event.status == "completed" else self.config.TOPIC_REMEDIATION_REQUESTED
        await self._publish(topic, event)

    async def publish_audit(self, event: AuditEvent):
        await self._publish(self.config.TOPIC_AUDIT_EVENTS, event)

    async def publish_dlq(self, payload: Any, reason: str):
        """Route unparseable or poison-pill payloads to Dead Letter Queue topic."""
        if not self.producer:
            return
        from datetime import datetime, timezone
        dlq_payload = {
            "payload": payload,
            "error_reason": reason,
            "failed_at": datetime.now(timezone.utc).isoformat(),
        }
        try:
            await self.producer.send_and_wait(self.config.TOPIC_TELEMETRY_DLQ, dlq_payload)
            logger.warning(f"Routed poisoned message to DLQ: {reason}")
        except Exception as e:
            logger.error(f"Failed to publish to DLQ: {e}")


_producer_instance = KafkaProducerService()

def get_kafka_producer() -> KafkaProducerService:
    return _producer_instance
