"""Event bus envelope validation and after-commit outbox, ``SPEC.md`` 3.1."""

from datetime import datetime, timezone
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.event_bus.outbox import schedule_publish
from app.event_bus.publisher import parse_stream_fields, publish_event
from app.event_bus.schemas import EventType


def test_publish_validates_without_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.event_bus.publisher.get_settings",
        lambda: type("S", (), {"redis_url": None})(),
    )
    assert (
        publish_event(
            EventType.DOCUMENT_CLASSIFIED,
            {
                "document_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
                "classification_id": "11111111-1111-1111-1111-111111111111",
                "sensitivity_label": "CONFIDENTIAL",
            },
        )
        is None
    )


def test_publish_rejects_empty_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.event_bus.publisher.get_settings",
        lambda: type("S", (), {"redis_url": None})(),
    )
    with pytest.raises(ValidationError):
        publish_event(EventType.RISK_TRIGGER, {})


def test_publish_rejects_unexpected_keys(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "app.event_bus.publisher.get_settings",
        lambda: type("S", (), {"redis_url": None})(),
    )
    with pytest.raises(ValidationError):
        publish_event(EventType.TRUST_UPDATED, {"unexpected": 1})


def test_parse_stream_fields_round_trip() -> None:
    envelope = parse_stream_fields(
        {
            "event_type": "document.classified",
            "occurred_at": datetime(2026, 9, 14, tzinfo=timezone.utc).isoformat(),
            "payload": (
                '{"document_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",'
                ' "classification_id": "11111111-1111-1111-1111-111111111111",'
                ' "sensitivity_label": "CONFIDENTIAL"}'
            ),
        }
    )
    assert envelope.event_type is EventType.DOCUMENT_CLASSIFIED
    assert envelope.payload["sensitivity_label"] == "CONFIDENTIAL"


def test_schedule_publish_flushes_after_commit(
    monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    published: list[tuple[EventType, dict]] = []

    def capture(event_type: EventType, payload: dict, **_kwargs: object) -> str | None:
        published.append((event_type, payload))
        return None

    monkeypatch.setattr("app.event_bus.outbox.publish_event", capture)
    schedule_publish(
        db_session,
        EventType.SCHEDULE_TICK,
        {
            "scheduled": True,
            "tick_at": datetime(2026, 9, 14, tzinfo=timezone.utc).isoformat(),
        },
    )
    assert published == []
    db_session.commit()
    assert len(published) == 1
    assert published[0][0] is EventType.SCHEDULE_TICK


def test_schedule_publish_discards_on_rollback(
    monkeypatch: pytest.MonkeyPatch, db_session: Session
) -> None:
    published: list[object] = []

    monkeypatch.setattr(
        "app.event_bus.outbox.publish_event",
        lambda *args, **kwargs: published.append(args) or None,
    )
    schedule_publish(
        db_session,
        EventType.DOCUMENT_CLASSIFIED,
        {
            "document_id": str(uuid4()),
            "classification_id": str(uuid4()),
            "sensitivity_label": "PUBLIC",
        },
    )
    db_session.rollback()
    assert published == []
