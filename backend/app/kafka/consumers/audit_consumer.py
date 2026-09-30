"""Audit Kafka consumer."""

import logging
from ..consumer import BaseKafkaConsumer
from ..config import get_kafka_config
from ..events import AuditEvent

logger = logging.getLogger(__name__)

class AuditConsumer(BaseKafkaConsumer):
    def __init__(self):
        config = get_kafka_config()
        super().__init__(
            topics=[config.TOPIC_AUDIT_EVENTS],
            group_id=config.CG_AUDIT,
            config=config
        )
        
    async def handle_message(self, topic: str, value: dict):
        try:
            event = AuditEvent(**value)
            # In a real app, write this to a persistent database table.
            # Here we log it to a structured audit log (standard out/file).
            logger.info(f"AUDIT LOG: {event.timestamp} | {event.actor} | {event.event_type} | {event.details}")
        except Exception as e:
            logger.error(f"Failed to process audit event: {e}")
