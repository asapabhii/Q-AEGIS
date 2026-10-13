"""Outbox relay: drains committed ``event_outbox`` rows to Redis Streams.

This is the "polling publisher" half of the transactional outbox. A background
thread claims due pending rows (``FOR UPDATE SKIP LOCKED``), publishes each to the
stream, and records the outcome: ``sent`` with the stream id on success, a backed-
off retry on a transient failure, or ``dead`` once retries are exhausted.

Durability guarantee. A row committed by :func:`app.event_bus.outbox.schedule_publish`
survives a process crash, so the relay delivers it on the next start — the event
is not lost the way an in-memory queue would lose it. Delivery is **at-least-once**:
if the process dies after ``xadd`` succeeds but before the ``sent`` update commits,
the row is still pending and is published again on restart. Consumers are
idempotent by design, so a duplicate is a no-op.

The thread only runs when both Redis and the database are configured. Tests and
CI drive :func:`drain_once` directly for deterministic, thread-free assertions.
"""

from __future__ import annotations

import logging
import threading
from dataclasses import dataclass
from datetime import datetime, timezone

from app.config import get_settings
from app.db.repositories import outbox as outbox_repo
from app.db.session import DatabaseNotConfiguredError, get_sessionmaker
from app.event_bus.publisher import is_bus_configured, publish_event
from app.event_bus.schemas import EventType

logger = logging.getLogger(__name__)

_wake = threading.Event()
_stop = threading.Event()
_thread: threading.Thread | None = None


@dataclass(frozen=True)
class DrainResult:
    """Outcome of one :func:`drain_once` pass."""

    claimed: int = 0
    sent: int = 0
    retried: int = 0
    dead: int = 0

    @property
    def failed(self) -> int:
        """Rows that did not publish this pass (retried plus dead-lettered)."""
        return self.retried + self.dead


def nudge() -> None:
    """Wake the relay thread to drain now instead of waiting for the next poll."""
    _wake.set()


def drain_once(
    *,
    session_factory=None,
    now: datetime | None = None,
) -> DrainResult:
    """Publish one batch of due outbox rows and record each outcome.

    Claims up to ``OUTBOX_RELAY_BATCH_SIZE`` due pending rows under
    ``FOR UPDATE SKIP LOCKED``, publishes each, and marks it ``sent``/retried/
    ``dead`` — all in one transaction, so the row locks are held across the
    publish and released together on commit. Returns per-outcome counts.

    A no-op (returns zeros) when Redis or the database is not configured: there is
    nowhere to publish to, so rows are left pending rather than being falsely
    marked sent.
    """
    if not is_bus_configured():
        return DrainResult()

    settings = get_settings()
    now = now or datetime.now(timezone.utc)
    try:
        factory = session_factory or get_sessionmaker()
    except DatabaseNotConfiguredError:
        return DrainResult()

    session = factory()
    sent = retried = dead = 0
    try:
        rows = outbox_repo.claim_batch(
            session, limit=settings.outbox_relay_batch_size, now=now
        )
        for row in rows:
            try:
                stream_id = publish_event(
                    EventType(row.event_type),
                    row.payload,
                    occurred_at=row.occurred_at,
                )
            except (
                Exception
            ) as exc:  # noqa: BLE001 - one bad row must not stall the rest
                outbox_repo.mark_failed(
                    session,
                    row,
                    error=f"{type(exc).__name__}: {exc}",
                    max_attempts=settings.outbox_max_attempts,
                    base_seconds=settings.outbox_retry_base_seconds,
                    cap_seconds=settings.outbox_retry_cap_seconds,
                    now=now,
                )
                dead += 1 if row.status == "dead" else 0
                retried += 0 if row.status == "dead" else 1
                continue

            if stream_id is None:
                # Bus went away between the guard above and the publish. Treat as
                # a transient failure so the row is retried, never marked sent.
                outbox_repo.mark_failed(
                    session,
                    row,
                    error="publish returned no stream id (bus unconfigured)",
                    max_attempts=settings.outbox_max_attempts,
                    base_seconds=settings.outbox_retry_base_seconds,
                    cap_seconds=settings.outbox_retry_cap_seconds,
                    now=now,
                )
                dead += 1 if row.status == "dead" else 0
                retried += 0 if row.status == "dead" else 1
                continue

            outbox_repo.mark_sent(session, row, stream_id=stream_id, now=now)
            sent += 1

        session.commit()
        return DrainResult(claimed=len(rows), sent=sent, retried=retried, dead=dead)
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _drain_until_empty() -> None:
    """Drain repeated batches until no due rows remain or shutdown is requested."""
    while not _stop.is_set():
        try:
            result = drain_once()
        except Exception:  # noqa: BLE001 - relay must not die on one bad pass
            logger.exception("outbox relay drain failed")
            return
        if result.dead:
            logger.warning("outbox relay dead-lettered %d event(s)", result.dead)
        if result.claimed == 0:
            return


def _loop() -> None:
    interval = get_settings().outbox_relay_interval_seconds
    while not _stop.is_set():
        _drain_until_empty()
        # Wake either on the poll interval or on an after-commit nudge, whichever
        # comes first, so a just-committed event publishes without waiting a full
        # interval.
        _wake.wait(timeout=interval)
        _wake.clear()


def start_outbox_relay() -> None:
    """Start the background relay when Redis and a poll interval are configured."""
    global _thread
    if not is_bus_configured():
        logger.info("outbox relay disabled (REDIS_URL unset)")
        return
    if get_settings().outbox_relay_interval_seconds <= 0:
        logger.info("outbox relay thread disabled (interval<=0)")
        return
    if _thread is not None and _thread.is_alive():
        return
    _stop.clear()
    _wake.clear()
    _thread = threading.Thread(target=_loop, name="outbox-relay", daemon=True)
    _thread.start()
    logger.info("outbox relay started")


def stop_outbox_relay() -> None:
    """Signal the relay thread to stop (tests / shutdown)."""
    _stop.set()
    _wake.set()
