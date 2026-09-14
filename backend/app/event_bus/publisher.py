"""Redis Streams publisher, ``SPEC.md`` 3.1.

When ``REDIS_URL`` is unset the publisher is a no-op that still validates the
envelope, so unit tests and the CI image smoke test do not require Redis. A
missing broker must never invent a successful side effect that did not happen:
callers that need durable delivery check :func:`is_bus_configured`.
"""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ValidationError

from app.config import get_settings
from app.event_bus.schemas import (
    DocumentClassifiedPayload,
    DocumentUploadedPayload,
    EventEnvelope,
    EventType,
    RiskTriggerPayload,
    ScheduleTickPayload,
    TrustUpdatedPayload,
)

logger = logging.getLogger(__name__)

#: Single stream for P0. Consumer groups fan out by module later.
STREAM_KEY = "qaegis:events"

_PAYLOAD_MODELS: dict[EventType, type[BaseModel]] = {
    EventType.DOCUMENT_UPLOADED: DocumentUploadedPayload,
    EventType.DOCUMENT_CLASSIFIED: DocumentClassifiedPayload,
    EventType.RISK_TRIGGER: RiskTriggerPayload,
    EventType.TRUST_UPDATED: TrustUpdatedPayload,
    EventType.SCHEDULE_TICK: ScheduleTickPayload,
}


def is_bus_configured() -> bool:
    """True when a Redis URL is present and a client can be created."""
    return bool(get_settings().redis_url)


def validate_event_payload(
    event_type: EventType, payload: dict[str, Any]
) -> dict[str, Any]:
    """Validate ``payload`` against the closed model for ``event_type``.

    Returns JSON-serialisable primitives (UUIDs and datetimes as strings via
    ``model_dump(mode="json")``).
    """
    model = _PAYLOAD_MODELS[event_type]
    return model.model_validate(payload).model_dump(mode="json")


def publish_event(
    event_type: EventType,
    payload: dict[str, Any],
    *,
    occurred_at: datetime | None = None,
) -> str | None:
    """Validate and append one event to the stream.

    Returns the Redis stream entry id, or ``None`` when the bus is not
    configured. Always validates ``payload`` against the event-specific model
    before any I/O so mis-shaped events fail locally.

    Args:
        event_type: One of the closed :class:`EventType` values.
        payload: Event body matching the type's Pydantic model.
        occurred_at: Event time; defaults to UTC now.

    Returns:
        Stream id string, or ``None`` if Redis is not configured.

    Raises:
        ValidationError: if the payload or envelope is invalid.
        RuntimeError: if Redis is configured but the write fails.
    """
    validated = validate_event_payload(event_type, payload)
    envelope = EventEnvelope(
        event_type=event_type,
        occurred_at=occurred_at or datetime.now(timezone.utc),
        payload=validated,
    )
    if not is_bus_configured():
        logger.debug(
            "event bus not configured; validated %s but did not publish",
            event_type.value,
        )
        return None

    try:
        import redis
    except ImportError as exc:  # pragma: no cover - dependency is declared
        raise RuntimeError("redis package is required when REDIS_URL is set") from exc

    client = redis.Redis.from_url(
        get_settings().redis_url,  # type: ignore[arg-type]
        decode_responses=True,
    )
    try:
        entry_id = client.xadd(
            STREAM_KEY,
            {
                "event_type": envelope.event_type.value,
                "occurred_at": envelope.occurred_at.isoformat(),
                "payload": json.dumps(envelope.payload, default=str),
            },
        )
    except Exception as exc:
        raise RuntimeError(f"failed to publish {event_type.value}: {exc}") from exc
    finally:
        client.close()

    return str(entry_id)


def parse_stream_fields(fields: dict[str, str]) -> EventEnvelope:
    """Rebuild an envelope from Redis stream field map. Validates on the way in."""
    try:
        raw_payload = json.loads(fields["payload"])
        event_type = EventType(fields["event_type"])
        validated = validate_event_payload(event_type, raw_payload)
        return EventEnvelope(
            event_type=event_type,
            occurred_at=datetime.fromisoformat(fields["occurred_at"]),
            payload=validated,
        )
    except (KeyError, ValueError, json.JSONDecodeError, ValidationError) as exc:
        raise ValueError(f"invalid stream fields: {exc}") from exc
