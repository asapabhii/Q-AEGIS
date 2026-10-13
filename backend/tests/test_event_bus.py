"""Event bus envelope validation and the transactional outbox, ``SPEC.md`` 3.1."""

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


def test_schedule_publish_persists_pending_row(db_session: Session) -> None:
    """schedule_publish writes a durable pending outbox row in the caller's tx."""
    from app.db.models import EventOutbox
    from app.db.models.outbox import OUTBOX_STATUS_PENDING

    schedule_publish(
        db_session,
        EventType.SCHEDULE_TICK,
        {
            "scheduled": True,
            "tick_at": datetime(2026, 9, 14, tzinfo=timezone.utc).isoformat(),
        },
    )
    # Flushed within the transaction, so it is queryable immediately without a
    # commit — and it is the row a relay would later drain.
    rows = db_session.query(EventOutbox).all()
    assert len(rows) == 1
    row = rows[0]
    assert row.event_type == EventType.SCHEDULE_TICK.value
    assert row.status == OUTBOX_STATUS_PENDING
    assert row.attempts == 0
    assert row.payload["scheduled"] is True


def test_schedule_publish_row_rolls_back(db_session: Session) -> None:
    """A rolled-back transaction leaves no outbox row: no event is published."""
    from app.db.models import EventOutbox

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
    assert db_session.query(EventOutbox).count() == 0


def _redis_settings_stub(**over):
    base = {
        "redis_url": "rediss://localhost:6379/0",
        "redis_ssl_ca_certs": None,
        "app_env": "local",
    }
    base.update(over)
    return type("S", (), base)()


def _capture_redis_from_url(monkeypatch: pytest.MonkeyPatch) -> dict:
    """Intercept redis.Redis.from_url and record the kwargs it was called with."""
    import redis

    captured: dict = {}

    def fake_from_url(url, **kwargs):
        captured["url"] = url
        captured["kwargs"] = kwargs
        return object()

    monkeypatch.setattr(redis.Redis, "from_url", staticmethod(fake_from_url))
    return captured


def test_redis_tls_local_allows_unverified(monkeypatch: pytest.MonkeyPatch) -> None:
    """APP_ENV=local accepts the self-signed compose CA unverified."""
    from app.event_bus import client

    monkeypatch.setattr(client, "get_settings", lambda: _redis_settings_stub())
    captured = _capture_redis_from_url(monkeypatch)
    client.redis_from_settings()
    assert captured["kwargs"]["ssl_cert_reqs"] == "none"
    assert captured["kwargs"]["ssl_check_hostname"] is False


def test_redis_tls_nonlocal_with_ca_verifies(monkeypatch: pytest.MonkeyPatch) -> None:
    """A non-local env with a CA configured verifies against it (no downgrade)."""
    from app.event_bus import client

    monkeypatch.setattr(
        client,
        "get_settings",
        lambda: _redis_settings_stub(
            app_env="production", redis_ssl_ca_certs="/ca.crt"
        ),
    )
    captured = _capture_redis_from_url(monkeypatch)
    client.redis_from_settings()
    assert captured["kwargs"]["ssl_ca_certs"] == "/ca.crt"
    assert "ssl_cert_reqs" not in captured["kwargs"]


def test_redis_tls_nonlocal_without_ca_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A non-local rediss:// with no CA fails closed instead of disabling TLS."""
    from app.event_bus import client

    monkeypatch.setattr(
        client,
        "get_settings",
        lambda: _redis_settings_stub(app_env="production", redis_ssl_ca_certs=None),
    )
    _capture_redis_from_url(monkeypatch)
    with pytest.raises(RuntimeError, match="REDIS_SSL_CA_CERTS"):
        client.redis_from_settings()
