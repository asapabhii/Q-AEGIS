"""Scheduled recompute helpers, ``SPEC.md`` 3.3 / FR-2."""

from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Document, RiskScore
from app.db.repositories import risk as risk_repo
from app.risk_engine.recompute import (
    recompute_document_from_latest,
    snapshot_from_stored,
)
from app.risk_engine.scheduler import _tick_once
from tests.factories import make_risk_score


def test_snapshot_from_stored_rederives_after_hours() -> None:
    """The refreshed wall-clock re-derives after_hours; the stored bool is
    never trusted. Stored ``after_hours`` is False, but a 22:00 UTC tick is
    03:30 in Asia/Kolkata — after hours — so the rebuilt snapshot flips to
    True, and the default timezone is applied when the row predates 0.2.0.
    """
    raw = {
        "actor_user_id": str(uuid4()),
        "device_id": "laptop-1",
        "device_is_new": True,
        "accessed_at": "2026-01-01T10:00:00+00:00",
        "after_hours": False,
    }
    tick = datetime(2026, 9, 14, 22, 0, tzinfo=timezone.utc)
    snap = snapshot_from_stored(raw, accessed_at=tick)
    assert snap.accessed_at == tick
    assert snap.device_is_new is True
    assert snap.after_hours is True
    assert snap.org_timezone == "Asia/Kolkata"


def test_snapshot_from_stored_honours_stored_timezone() -> None:
    """A stored non-default timezone drives the re-derivation."""
    raw = {
        "actor_user_id": str(uuid4()),
        "device_id": "laptop-1",
        "device_is_new": False,
        "accessed_at": "2026-01-01T10:00:00+00:00",
        "after_hours": True,
        "org_timezone": "UTC",
    }
    # 12:00 UTC is inside 09:00-18:00 on a Monday in UTC -> business hours.
    tick = datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc)
    snap = snapshot_from_stored(raw, accessed_at=tick)
    assert snap.org_timezone == "UTC"
    assert snap.after_hours is False


def test_recompute_document_appends_new_row(
    db_session: Session, registered_document: Document
) -> None:
    first = make_risk_score(db_session, registered_document)
    first_id = first.id
    db_session.flush()

    second = recompute_document_from_latest(
        db_session,
        registered_document.id,
        accessed_at=datetime(2026, 9, 14, 12, 0, tzinfo=timezone.utc),
    )
    assert second is not None
    assert second.id != first_id
    assert second.context_snapshot["accessed_at"].startswith("2026-09-14")
    assert risk_repo.get_risk_score(db_session, second.id) is not None
    rows = db_session.scalars(
        select(RiskScore).where(RiskScore.document_id == registered_document.id)
    ).all()
    assert len(rows) == 2


def test_tick_without_redis_calls_scheduled_recompute(monkeypatch) -> None:
    """Offline FR-2 path: ticker recomputes in-process when Redis is unset."""
    calls: list[datetime] = []

    monkeypatch.setattr(
        "app.risk_engine.scheduler.is_bus_configured",
        lambda: False,
    )
    monkeypatch.setattr(
        "app.risk_engine.recompute.run_scheduled_recompute",
        lambda *, now=None: calls.append(now) or 0,
    )
    _tick_once()
    assert len(calls) == 1
    assert calls[0].tzinfo is not None


def test_tick_with_redis_publishes_schedule_tick(monkeypatch) -> None:
    published: list[tuple] = []

    monkeypatch.setattr(
        "app.risk_engine.scheduler.is_bus_configured",
        lambda: True,
    )
    monkeypatch.setattr(
        "app.risk_engine.scheduler.publish_event",
        lambda event_type, payload: published.append((event_type, payload)),
    )
    _tick_once()
    assert len(published) == 1
    assert published[0][0].value == "schedule.tick"
    assert published[0][1]["scheduled"] is True
