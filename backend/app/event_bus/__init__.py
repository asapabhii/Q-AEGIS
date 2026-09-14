"""Ingestion / event bus, ``SPEC.md`` 3.1.

Decided 2026-09-14: Redis Streams, logged in ``docs/decisions.md``. Kafka is
deferred until partitioned multi-consumer-group scale is a measured need.

Publish and consume validate the same envelope schema. Downstream modules
subscribe independently rather than being called directly from each other.
"""

from app.event_bus.outbox import schedule_publish
from app.event_bus.publisher import publish_event, validate_event_payload
from app.event_bus.schemas import EventEnvelope, EventType

__all__ = [
    "EventEnvelope",
    "EventType",
    "publish_event",
    "schedule_publish",
    "validate_event_payload",
]
