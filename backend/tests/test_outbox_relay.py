"""Durable transactional outbox: relay drain, retry, and dead-letter recovery.

These run against a real committed Postgres (the ``migrated_scratch_engine``
fixture), not the shared rolled-back session, because the relay opens its own
connection exactly as it does in production: a row is only drainable once it is
*committed*, so a test that never commits would prove nothing. ``publish_event``
is the one seam stubbed here — the point under test is the outbox state machine,
not Redis I/O.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.db.models.outbox import (
    OUTBOX_STATUS_DEAD,
    OUTBOX_STATUS_PENDING,
    OUTBOX_STATUS_SENT,
    EventOutbox,
)
from app.db.repositories import outbox as outbox_repo
from app.event_bus import relay
from app.event_bus.schemas import EventType

_TICK_PAYLOAD = {
    "scheduled": True,
    "tick_at": datetime(2026, 9, 14, tzinfo=timezone.utc).isoformat(),
}


@pytest.fixture
def outbox_sm(migrated_scratch_engine: Engine) -> sessionmaker[Session]:
    """Session factory bound to a real, committable scratch database."""
    return sessionmaker(
        bind=migrated_scratch_engine, expire_on_commit=False, future=True
    )


def _enqueue_committed(
    sm: sessionmaker[Session], *, occurred_at: datetime | None = None
) -> str:
    """Enqueue one schedule-tick event and commit it. Returns the row id."""
    occurred = occurred_at or datetime.now(timezone.utc)
    with sm() as session:
        row = outbox_repo.enqueue(
            session,
            event_type=EventType.SCHEDULE_TICK.value,
            payload=_TICK_PAYLOAD,
            occurred_at=occurred,
        )
        row_id = str(row.id)
        session.commit()
    return row_id


def test_enqueue_persists_pending_row(outbox_sm: sessionmaker[Session]) -> None:
    row_id = _enqueue_committed(outbox_sm)
    with outbox_sm() as session:
        row = session.get(EventOutbox, row_id)
        assert row is not None
        assert row.status == OUTBOX_STATUS_PENDING
        assert row.attempts == 0
        assert row.stream_id is None
        assert row.published_at is None


def test_drain_publishes_and_marks_sent(
    outbox_sm: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    occurred = datetime(2026, 9, 20, 12, 0, tzinfo=timezone.utc)
    _enqueue_committed(outbox_sm, occurred_at=occurred)
    _enqueue_committed(outbox_sm, occurred_at=occurred)

    calls: list[tuple[EventType, dict, datetime | None]] = []

    def fake_publish(event_type, payload, *, occurred_at=None):
        calls.append((event_type, payload, occurred_at))
        return f"165-{len(calls)}"

    monkeypatch.setattr(relay, "is_bus_configured", lambda: True)
    monkeypatch.setattr(relay, "publish_event", fake_publish)

    result = relay.drain_once(session_factory=outbox_sm)

    assert result.claimed == 2
    assert result.sent == 2
    assert result.failed == 0
    assert len(calls) == 2
    # The relay publishes the original event, not a re-derived one: type and the
    # preserved occurred_at both travel through.
    assert calls[0][0] is EventType.SCHEDULE_TICK
    assert calls[0][2] == occurred

    with outbox_sm() as session:
        rows = session.query(EventOutbox).all()
        assert {r.status for r in rows} == {OUTBOX_STATUS_SENT}
        for row in rows:
            assert row.stream_id is not None
            assert row.published_at is not None
            assert row.attempts == 1


def test_drain_is_noop_without_bus(
    outbox_sm: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    _enqueue_committed(outbox_sm)
    published: list[object] = []
    monkeypatch.setattr(relay, "is_bus_configured", lambda: False)
    monkeypatch.setattr(
        relay, "publish_event", lambda *a, **k: published.append(a) or "x"
    )

    result = relay.drain_once(session_factory=outbox_sm)

    assert result == relay.DrainResult()
    assert published == []
    with outbox_sm() as session:
        assert session.query(EventOutbox).one().status == OUTBOX_STATUS_PENDING


def test_drain_retries_then_dead_letters(
    outbox_sm: sessionmaker[Session], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setenv("OUTBOX_MAX_ATTEMPTS", "2")
    monkeypatch.setenv("OUTBOX_RETRY_BASE_SECONDS", "10")
    from app.config import get_settings

    get_settings.cache_clear()

    t0 = datetime(2026, 9, 21, 0, 0, tzinfo=timezone.utc)
    row_id = _enqueue_committed(outbox_sm, occurred_at=t0)

    monkeypatch.setattr(relay, "is_bus_configured", lambda: True)

    def boom(*_a, **_k):
        raise RuntimeError("redis down")

    monkeypatch.setattr(relay, "publish_event", boom)

    first = relay.drain_once(session_factory=outbox_sm, now=t0)
    assert first.retried == 1
    assert first.dead == 0
    with outbox_sm() as session:
        row = session.get(EventOutbox, row_id)
        assert row.status == OUTBOX_STATUS_PENDING
        assert row.attempts == 1
        assert row.last_error and "redis down" in row.last_error
        # Backed off ~10s from t0; a drain at t0 would now skip it.
        assert row.next_attempt_at > t0

    # Not yet due: a drain before the backoff window claims nothing.
    assert relay.drain_once(session_factory=outbox_sm, now=t0).claimed == 0

    # Past the backoff window: second failure exhausts the 2-attempt budget.
    t1 = t0 + timedelta(seconds=30)
    second = relay.drain_once(session_factory=outbox_sm, now=t1)
    assert second.dead == 1
    with outbox_sm() as session:
        row = session.get(EventOutbox, row_id)
        assert row.status == OUTBOX_STATUS_DEAD
        assert row.attempts == 2

    # Dead rows are retained and recoverable, never dropped.
    with outbox_sm() as session:
        dead = outbox_repo.list_dead(session)
        assert [str(r.id) for r in dead] == [row_id]
        outbox_repo.requeue(session, row.id, now=t1)
        session.commit()
    with outbox_sm() as session:
        row = session.get(EventOutbox, row_id)
        assert row.status == OUTBOX_STATUS_PENDING
        assert row.attempts == 0


def test_claim_batch_skips_future_rows(outbox_sm: sessionmaker[Session]) -> None:
    now = datetime(2026, 9, 22, 0, 0, tzinfo=timezone.utc)
    with outbox_sm() as session:
        row = outbox_repo.enqueue(
            session,
            event_type=EventType.SCHEDULE_TICK.value,
            payload=_TICK_PAYLOAD,
            occurred_at=now + timedelta(hours=1),
        )
        session.commit()
        due_id = str(row.id)
    with outbox_sm() as session:
        claimed = outbox_repo.claim_batch(session, limit=10, now=now)
        assert [str(r.id) for r in claimed] == []
        # And it is claimable once its time arrives.
        later = outbox_repo.claim_batch(session, limit=10, now=now + timedelta(hours=2))
        assert [str(r.id) for r in later] == [due_id]
