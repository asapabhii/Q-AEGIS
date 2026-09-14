"""Event bus envelope validation, ``SPEC.md`` 3.1."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

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


def test_parse_stream_fields_round_trip() -> None:
    envelope = parse_stream_fields(
        {
            "event_type": "document.classified",
            "occurred_at": datetime(2026, 9, 14, tzinfo=timezone.utc).isoformat(),
            "payload": '{"document_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"}',
        }
    )
    assert envelope.event_type is EventType.DOCUMENT_CLASSIFIED
