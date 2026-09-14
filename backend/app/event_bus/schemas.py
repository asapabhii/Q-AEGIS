"""Validated event envelopes for Redis Streams, ``SPEC.md`` 3.1.

Extra keys are forbidden. Publish and consume share these models so a bad
payload fails at the edge rather than poisoning a subscriber.
"""

from datetime import datetime
from enum import Enum
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EventType(str, Enum):
    """Stream event names the P0 bus knows how to publish and consume."""

    DOCUMENT_UPLOADED = "document.uploaded"
    DOCUMENT_CLASSIFIED = "document.classified"
    RISK_TRIGGER = "risk.trigger"
    TRUST_UPDATED = "trust.updated"
    SCHEDULE_TICK = "schedule.tick"


class EventEnvelope(BaseModel):
    """One bus message. ``payload`` shape depends on ``event_type``."""

    model_config = ConfigDict(extra="forbid")

    event_type: EventType
    occurred_at: datetime
    payload: dict[str, Any] = Field(min_length=1)


class DocumentUploadedPayload(BaseModel):
    """``document.uploaded`` body, ``SPEC.md`` 3.1."""

    model_config = ConfigDict(extra="forbid")

    document_id: UUID
    uploaded_by: UUID
    storage_path: str | None = None


class DocumentClassifiedPayload(BaseModel):
    """Published after a classification row is committed."""

    model_config = ConfigDict(extra="forbid")

    document_id: UUID
    classification_id: UUID
    sensitivity_label: str


class RiskTriggerPayload(BaseModel):
    """Immediate recompute trigger: new device or after-hours access."""

    model_config = ConfigDict(extra="forbid")

    document_id: UUID
    actor_user_id: UUID
    device_id: str = Field(min_length=1, max_length=255)
    device_is_new: bool
    after_hours: bool
    accessed_at: datetime


class TrustUpdatedPayload(BaseModel):
    """Published when a new consensus row is written (FR-6 reselect signal)."""

    model_config = ConfigDict(extra="forbid")

    document_id: UUID
    trust_score_id: UUID
    consensus_value: str


class ScheduleTickPayload(BaseModel):
    """Periodic FR-2 heartbeat; consumers recompute each document's latest snapshot."""

    model_config = ConfigDict(extra="forbid")

    scheduled: bool = True
    tick_at: datetime
