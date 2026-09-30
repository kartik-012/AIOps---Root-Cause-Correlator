"""Kafka configuration."""

import os
from functools import lru_cache

class KafkaConfig:
    """Configuration for Kafka connection and topics."""
    
    BOOTSTRAP_SERVERS: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    
    # Topics
    TOPIC_TELEMETRY: str = "service.telemetry"
    TOPIC_ERRORS: str = "service.errors"
    TOPIC_INCIDENT_DETECTED: str = "incident.detected"
    TOPIC_INCIDENT_UPDATED: str = "incident.updated"
    TOPIC_REMEDIATION_REQUESTED: str = "remediation.requested"
    TOPIC_REMEDIATION_COMPLETED: str = "remediation.completed"
    TOPIC_AUDIT_EVENTS: str = "audit.events"
    TOPIC_TELEMETRY_DLQ: str = "service.telemetry.dlq"
    
    # Consumer Groups
    CG_TELEMETRY: str = "aiops-telemetry-consumer-group"
    CG_AUDIT: str = "aiops-audit-consumer-group"
    
    @classmethod
    def get_all_topics(cls) -> list[str]:
        return [
            cls.TOPIC_TELEMETRY,
            cls.TOPIC_ERRORS,
            cls.TOPIC_INCIDENT_DETECTED,
            cls.TOPIC_INCIDENT_UPDATED,
            cls.TOPIC_REMEDIATION_REQUESTED,
            cls.TOPIC_REMEDIATION_COMPLETED,
            cls.TOPIC_AUDIT_EVENTS,
            cls.TOPIC_TELEMETRY_DLQ,
        ]

@lru_cache()
def get_kafka_config() -> KafkaConfig:
    return KafkaConfig()
