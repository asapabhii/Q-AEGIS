"""After-commit event scheduling so Redis never races an open transaction.

Publishers call :func:`schedule_publish` while a session is open. The events
are validated immediately, then held on ``session.info`` until the transaction
commits. A rollback discards them.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import event
from sqlalchemy.orm import Session

from app.event_bus.publisher import publish_event, validate_event_payload
from app.event_bus.schemas import EventType

_PENDING_KEY = "qaegis_pending_events"
_LISTENER_ATTACHED = False


def schedule_publish(
    session: Session,
    event_type: EventType,
    payload: dict[str, Any],
    *,
    occurred_at: datetime | None = None,
) -> None:
    """Queue an event to publish after this session commits successfully.

    Validates the payload now so a bad shape fails inside the request, not
    after commit. Does not write to Redis until after commit.
    """
    validate_event_payload(event_type, payload)
    pending: list[tuple[EventType, dict[str, Any], datetime | None]] = (
        session.info.setdefault(_PENDING_KEY, [])
    )
    pending.append((event_type, payload, occurred_at))
    _ensure_listeners()


def _flush_pending(session: Session) -> None:
    pending = session.info.pop(_PENDING_KEY, [])
    for event_type, payload, occurred_at in pending:
        publish_event(event_type, payload, occurred_at=occurred_at)


def _discard_pending(session: Session) -> None:
    session.info.pop(_PENDING_KEY, None)


def _ensure_listeners() -> None:
    global _LISTENER_ATTACHED
    if _LISTENER_ATTACHED:
        return

    @event.listens_for(Session, "after_commit")
    def _after_commit(session: Session) -> None:
        _flush_pending(session)

    @event.listens_for(Session, "after_rollback")
    def _after_rollback(session: Session) -> None:
        _discard_pending(session)

    _LISTENER_ATTACHED = True
