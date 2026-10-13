"""Enqueue and drain the transactional outbox, ``SPEC.md`` 3.1.

The side-effecting half of the outbox pattern. :func:`enqueue` writes an event
row in the caller's transaction (so it commits atomically with the domain
change); the claim/mark functions are what the relay
(:mod:`app.event_bus.relay`) uses to publish committed rows exactly-once-per-send
under concurrency.

Concurrency safety rests on ``SELECT ... FOR UPDATE SKIP LOCKED``: two relay
workers claiming at the same instant take disjoint row sets rather than both
grabbing the same row and double-publishing. A row a worker holds is invisible to
the other until the holding transaction commits or rolls back.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.outbox import (
    OUTBOX_STATUS_DEAD,
    OUTBOX_STATUS_PENDING,
    OUTBOX_STATUS_SENT,
    EventOutbox,
)


def enqueue(
    session: Session,
    *,
    event_type: str,
    payload: dict[str, Any],
    occurred_at: datetime,
) -> EventOutbox:
    """Add one pending event to the outbox without committing.

    Does not commit, on purpose: the caller's transaction is what makes the
    domain change and its announcement atomic. Committing here would let the
    business write roll back while the event survived to be published — exactly
    the dual-write bug the outbox exists to prevent.

    Args:
        session: Active session inside the caller's transaction.
        event_type: The :class:`app.event_bus.schemas.EventType` value.
        payload: Validated, JSON-primitive event body.
        occurred_at: Event time, preserved onto the published envelope.

    Returns:
        The pending row, flushed so its server-generated ``id`` is populated.
    """
    row = EventOutbox(
        event_type=event_type,
        payload=payload,
        occurred_at=occurred_at,
        status=OUTBOX_STATUS_PENDING,
        attempts=0,
        next_attempt_at=occurred_at,
    )
    session.add(row)
    # Flush, not commit: surfaces any constraint violation here, attributable to
    # this write, and populates the id without ending the caller's transaction.
    session.flush()
    return row


def claim_batch(
    session: Session, *, limit: int, now: datetime | None = None
) -> list[EventOutbox]:
    """Lock and return up to ``limit`` due pending rows, oldest first.

    ``FOR UPDATE SKIP LOCKED`` is the whole point: concurrent relay workers take
    disjoint rows instead of contending for the same one, so horizontal scaling
    needs no coordination beyond the database. The returned rows are locked for
    the life of ``session``'s transaction; the caller must commit or roll back to
    release them.
    """
    now = now or datetime.now(timezone.utc)
    stmt = (
        select(EventOutbox)
        .where(EventOutbox.status == OUTBOX_STATUS_PENDING)
        .where(EventOutbox.next_attempt_at <= now)
        .order_by(EventOutbox.created_at)
        .limit(limit)
        .with_for_update(skip_locked=True)
    )
    return list(session.scalars(stmt).all())


def mark_sent(
    session: Session,
    row: EventOutbox,
    *,
    stream_id: str,
    now: datetime | None = None,
) -> None:
    """Record a successful publish: status ``sent`` with its stream evidence."""
    now = now or datetime.now(timezone.utc)
    row.status = OUTBOX_STATUS_SENT
    row.attempts += 1
    row.stream_id = stream_id
    row.published_at = now
    row.last_error = None
    session.flush()


def mark_failed(
    session: Session,
    row: EventOutbox,
    *,
    error: str,
    max_attempts: int,
    base_seconds: float,
    cap_seconds: float,
    now: datetime | None = None,
) -> None:
    """Record a failed publish: back off, or dead-letter once retries run out.

    A dead-lettered row (``status='dead'``) is retained, never deleted: an
    operator can inspect ``last_error`` and requeue it with :func:`requeue`. That
    is the difference between a durable outbox and a queue that quietly drops
    poison messages.
    """
    now = now or datetime.now(timezone.utc)
    row.attempts += 1
    row.last_error = error[:2000]
    if row.attempts >= max_attempts:
        row.status = OUTBOX_STATUS_DEAD
    else:
        delay = min(base_seconds * (2 ** (row.attempts - 1)), cap_seconds)
        row.next_attempt_at = now + timedelta(seconds=delay)
    session.flush()


def requeue(
    session: Session, outbox_id: UUID, *, now: datetime | None = None
) -> EventOutbox | None:
    """Return a dead-lettered row to the pending set for another attempt.

    Resets the attempt counter and makes the row due immediately. Returns the row,
    or ``None`` if no row with that id exists. A no-op on a row that is not
    ``dead`` would silently reset a live retry schedule, so callers that only mean
    to recover the dead-letter set should check status first; this function itself
    requeues whatever id it is given.
    """
    now = now or datetime.now(timezone.utc)
    row = session.get(EventOutbox, outbox_id)
    if row is None:
        return None
    row.status = OUTBOX_STATUS_PENDING
    row.attempts = 0
    row.next_attempt_at = now
    row.last_error = None
    session.flush()
    return row


def list_dead(session: Session, *, limit: int = 100) -> list[EventOutbox]:
    """Return dead-lettered rows, oldest first, for operator triage."""
    stmt = (
        select(EventOutbox)
        .where(EventOutbox.status == OUTBOX_STATUS_DEAD)
        .order_by(EventOutbox.created_at)
        .limit(limit)
    )
    return list(session.scalars(stmt).all())


def count_by_status(session: Session) -> dict[str, int]:
    """Return a ``{status: count}`` map for health/metrics surfaces."""
    from sqlalchemy import func as sa_func

    stmt = select(EventOutbox.status, sa_func.count()).group_by(EventOutbox.status)
    return {status: int(count) for status, count in session.execute(stmt).all()}
