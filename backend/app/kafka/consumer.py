"""Base Kafka consumer."""

import abc
import json
import logging
import asyncio
from typing import List
from aiokafka import AIOKafkaConsumer

from .config import KafkaConfig, get_kafka_config

logger = logging.getLogger(__name__)

class BaseKafkaConsumer(abc.ABC):
    """Abstract base class for Kafka consumers."""
    
    def __init__(self, topics: List[str], group_id: str, config: KafkaConfig = None):
        self.topics = topics
        self.group_id = group_id
        self.config = config or get_kafka_config()
        self.consumer = None
        self._running = False
        self._task = None
        
    async def start(self):
        """Start the consumer and begin listening to topics."""
        try:
            self.consumer = AIOKafkaConsumer(
                *self.topics,
                bootstrap_servers=self.config.BOOTSTRAP_SERVERS,
                group_id=self.group_id,
                value_deserializer=lambda m: json.loads(m.decode('utf-8')),
                auto_offset_reset="earliest"
            )
            await self.consumer.start()
            self._running = True
            logger.info(f"Kafka Consumer {self.__class__.__name__} started for topics {self.topics}")
            self._task = asyncio.create_task(self._consume_loop())
        except Exception as e:
            logger.error(f"Failed to start consumer {self.__class__.__name__}: {e}")
            self.consumer = None
            
    async def stop(self):
        """Stop the consumer."""
        self._running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        if self.consumer:
            await self.consumer.stop()
            logger.info(f"Kafka Consumer {self.__class__.__name__} stopped.")
            self.consumer = None
            
    async def _consume_loop(self):
        """Internal loop to consume messages."""
        try:
            async for msg in self.consumer:
                if not self._running:
                    break
                try:
                    await self.handle_message(msg.topic, msg.value)
                except Exception as e:
                    logger.error(f"Error handling message from {msg.topic} in {self.__class__.__name__}: {e}")
        except Exception as e:
            logger.error(f"Consumer loop error in {self.__class__.__name__}: {e}")
            # Real app might want to reconnect here

    @abc.abstractmethod
    async def handle_message(self, topic: str, value: dict):
        """Handle an incoming message."""
        pass
