"""``event_outbox`` — durable transactional outbox for the event bus (``SPEC.md`` 3.1).

Not one of the twelve core domain tables. This is delivery infrastructure: the
transactional-outbox pattern (Richardson, *Microservices Patterns*), which closes
the dual-write gap between committing a domain change and publishing the event
that announces it.

The problem it solves, concretely: a request classifies a document (a Postgres
write) and must announce ``document.classified`` on Redis. Doing both as two
independent side effects means a crash *between* them either loses the event
(commit, then die before publish) or publishes a lie (publish, then the
transaction rolls back). Writing the event as a row in **this** table, inside the
same transaction as the domain change, makes the two atomic: they commit together
or not at all. A separate relay (:mod:`app.event_bus.relay`) then reads committed
rows and publishes them, marking each ``sent`` — or, after
``OUTBOX_MAX_ATTEMPTS`` failures, ``dead`` for inspection.

Delivery is therefore **at-least-once**: a crash after publishing but before the
``sent`` update re-publishes on restart. Consumers are idempotent by design (the
FR-6 reselect keys on ``trust_score_id``; schedule ticks are time-stamped), so a
duplicate is a no-op rather than a fault.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    Index,
    Integer,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, created_timestamp, jsonb_column, uuid_primary_key

#: Outbox row lifecycle. A row is born ``PENDING``; the relay moves it to ``SENT``
#: on a successful publish, or to ``DEAD`` once it has exhausted its retries. These
#: are the only three values the CHECK constraint admits.
OUTBOX_STATUS_PENDING = "pending"
OUTBOX_STATUS_SENT = "sent"
OUTBOX_STATUS_DEAD = "dead"
OUTBOX_STATUSES = (OUTBOX_STATUS_PENDING, OUTBOX_STATUS_SENT, OUTBOX_STATUS_DEAD)

#: Length of a hex-encoded SHA-256 digest, matching ``audit_log`` hash columns.
HASH_HEX_LENGTH = 64


class EventOutbox(Base):
    """One event awaiting (or having completed) publication to the bus.

    Written in the caller's transaction by
    :func:`app.event_bus.outbox.schedule_publish`, drained by
    :mod:`app.event_bus.relay`. Status is a ``varchar`` with a CHECK rather than a
    Postgres enum: the value set is fixed and tiny, and a CHECK keeps the whole
    table self-contained in one migration without a separate type to create and
    drop.
    """

    __tablename__ = "event_outbox"
    __table_args__ = (
        CheckConstraint(
            "status IN ('pending', 'sent', 'dead')",
            name="valid_status",
        ),
        CheckConstraint("attempts >= 0", name="attempts_non_negative"),
        # The relay's hot query is "which pending rows are due now, oldest
        # first". A partial index over only pending rows keeps it small and
        # stops sent/dead history from bloating it as the table grows.
        Index(
            "ix_event_outbox_due",
            "next_attempt_at",
            "created_at",
            postgresql_where=text("status = 'pending'"),
        ),
    )

    id: Mapped[UUID] = uuid_primary_key()
    # The EventType value, e.g. "document.classified". String, mirroring
    # audit_log.event_type: the event vocabulary is app.event_bus.schemas.EventType
    # and gating each new type behind a migration would be friction for no safety.
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    # The validated, JSON-primitive payload exactly as it will be published. The
    # relay revalidates on the way out, so a schema drift is caught, not shipped.
    payload: Mapped[dict[str, Any]] = jsonb_column()
    # The original event time, preserved so the published envelope reflects when
    # the event happened, not when the relay got to it.
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, server_default=OUTBOX_STATUS_PENDING, index=True
    )
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    # When this row next becomes eligible for a publish attempt. Set forward on
    # each failure by exponential backoff; defaults to now so a fresh row is due
    # immediately.
    next_attempt_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    # Last publish failure, kept for operators triaging the dead-letter set. Null
    # until the first failure.
    last_error: Mapped[str | None] = mapped_column(Text, nullable=True)
    # The Redis stream entry id returned by a successful publish, and the time it
    # happened. Both null until the row is sent; together they are the evidence
    # that delivery actually occurred rather than being assumed.
    stream_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_at: Mapped[datetime] = created_timestamp(index=True)
