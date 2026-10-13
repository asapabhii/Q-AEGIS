"""Transactional-outbox write path, ``SPEC.md`` 3.1.

Publishers call :func:`schedule_publish` while a session is open. The event is
validated immediately (so a bad shape fails inside the request, not later in a
background thread) and written to the ``event_outbox`` table **in the caller's
transaction**. It is therefore durable the instant the caller commits: if the
process dies before the event reaches Redis, the relay (:mod:`app.event_bus.relay`)
publishes it on restart. A rollback discards the row with the rest of the
transaction — no separate cleanup, no lost or phantom events.

This replaces an earlier in-memory scheme that held events on ``session.info``
and published them from an ``after_commit`` hook. That scheme lost every pending
event if the process died between commit and publish; persisting to a table
closes that gap. The ``after_commit`` hook here now only *nudges* the relay to
drain promptly — correctness no longer depends on it running.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.db.repositories import outbox as outbox_repo
from app.event_bus.publisher import validate_event_payload
from app.event_bus.schemas import EventType

_NUDGE_KEY = "qaegis_outbox_nudge"
_LISTENER_ATTACHED = False


def schedule_publish(
    session: Session,
    event_type: EventType,
    payload: dict[str, Any],
    *,
    occurred_at: datetime | None = None,
) -> None:
    """Persist an event to the outbox in this transaction, to publish on commit.

    Validates the payload now against the event's closed model, then writes it to
    ``event_outbox``. Nothing is sent to Redis here; the relay drains committed
    rows. Because the row lives in the caller's transaction, the event is
    published if and only if the transaction commits.

    Args:
        session: Active session inside the caller's transaction.
        event_type: One of the closed :class:`EventType` values.
        payload: Event body matching the type's Pydantic model.
        occurred_at: Event time; defaults to UTC now.

    Raises:
        ValidationError: if ``payload`` does not match ``event_type``'s model.
    """
    validated = validate_event_payload(event_type, payload)
    occurred = occurred_at or datetime.now(timezone.utc)
    outbox_repo.enqueue(
        session,
        event_type=event_type.value,
        payload=validated,
        occurred_at=occurred,
    )
    session.info[_NUDGE_KEY] = True
    _ensure_listeners()


def _ensure_listeners() -> None:
    """Attach the one-time after-commit nudge listener.

    The listener only wakes the relay early; it never publishes. Attached lazily
    and once (guarded by a module flag) so importing this module has no global
    side effect and tests that never enqueue never register a listener.
    """
    global _LISTENER_ATTACHED
    if _LISTENER_ATTACHED:
        return

    @event.listens_for(Session, "after_commit")
    def _after_commit(session: Session) -> None:
        if not session.info.pop(_NUDGE_KEY, False):
            return
        # Best-effort, non-fatal: a nudge failure only delays delivery to the
        # next relay poll. Never let it escape into the committing caller.
        try:
            from app.event_bus.relay import nudge

            nudge()
        except Exception:  # noqa: BLE001 - latency optimisation, not correctness
            pass

    @event.listens_for(Session, "after_rollback")
    def _after_rollback(session: Session) -> None:
        session.info.pop(_NUDGE_KEY, None)

    _LISTENER_ATTACHED = True
