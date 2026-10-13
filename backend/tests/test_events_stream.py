"""Tests for the SSE events route helpers, ``SPEC.md`` 3.1.

``/events/stream`` streams forever, so the endpoint itself is not driven here;
its two testable helpers are:

* :func:`_authorize` -- the role gate. Membership in ``_STREAM_ROLES`` is the
  logic that belongs to this module (``authenticate_user`` is covered by the
  auth tests), so it is isolated by injecting a resolved user of a chosen role.
* :func:`_poll_inventory` -- the Redis-free fallback. It is a real async
  generator over a real database session: seeding a document must flip the
  emitted fingerprint from a ``ping`` (unchanged) to an ``inventory`` frame
  (changed). ``session_scope`` is redirected at the transactional test session
  so the seeded rows roll back; ``asyncio.sleep`` is neutralised so the 3s poll
  interval does not slow the suite.

The Redis ``XREAD`` fan-out (:func:`_redis_events`) needs a live broker and is
left to the integration environment, mirroring the liboqs/Redis gating pattern.
"""

from __future__ import annotations

import asyncio
import json
from contextlib import contextmanager
from types import SimpleNamespace
from typing import Iterator

import pytest
from fastapi import HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.routes import events
from app.db.enums import UserRole
from app.db.models import Document, User
from app.db.repositories import documents as documents_repo


def _event_name(frame: str) -> str:
    return frame.split("\n", 1)[0].removeprefix("event: ")


def _event_data(frame: str) -> dict:
    for line in frame.splitlines():
        if line.startswith("data: "):
            return json.loads(line[len("data: ") :])
    raise AssertionError(f"no data line in frame: {frame!r}")


# ---------------------------------------------------------------------------
# _authorize: role gate
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "role",
    [
        UserRole.SECURITY_ADMIN,
        UserRole.SECURITY_ANALYST,
        UserRole.AUDITOR,
        UserRole.CISO,
        UserRole.ENGINEER,
    ],
)
def test_authorize_admits_stream_roles(
    role: UserRole, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        events,
        "authenticate_user",
        lambda session, **kwargs: SimpleNamespace(role=role),
    )
    assert events._authorize(None, role.value) is role


@pytest.mark.parametrize(
    "role",
    [UserRole.DATA_OWNER, UserRole.COMPLIANCE_OFFICER],
)
def test_authorize_denies_non_stream_roles(
    role: UserRole, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(
        events,
        "authenticate_user",
        lambda session, **kwargs: SimpleNamespace(role=role),
    )
    with pytest.raises(HTTPException) as excinfo:
        events._authorize(None, role.value)
    assert excinfo.value.status_code == 403


# ---------------------------------------------------------------------------
# _poll_inventory: DB-only fallback fingerprint / change signal
# ---------------------------------------------------------------------------


def _redirect_session_scope(monkeypatch: pytest.MonkeyPatch, session: Session) -> None:
    """Point the helper's ``session_scope`` at the test's transaction."""

    @contextmanager
    def _scope() -> Iterator[Session]:
        yield session

    monkeypatch.setattr(events, "session_scope", _scope)


def _neutralise_sleep(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _no_sleep(_seconds: float) -> None:
        return None

    monkeypatch.setattr(events.asyncio, "sleep", _no_sleep)


def _fingerprint_count(frame: str) -> int:
    """The leading ``<count>`` of the ``<count>:<timestamp>`` fingerprint."""
    return int(_event_data(frame)["fingerprint"].split(":", 1)[0])


def test_poll_inventory_first_frame_carries_fingerprint(
    db_session: Session,
    seeded_users: dict[UserRole, User],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _redirect_session_scope(monkeypatch, db_session)
    documents_repo.register_document(
        db_session,
        uploaded_by=seeded_users[UserRole.DATA_OWNER].id,
        filename="quarterly-report.pdf",
    )
    db_session.flush()

    async def _first() -> str:
        gen = events._poll_inventory()
        try:
            return await gen.__anext__()
        finally:
            await gen.aclose()

    frame = asyncio.run(_first())

    # The first frame is always an inventory frame (no prior fingerprint), and
    # its fingerprint encodes the live document count that the same session sees.
    assert _event_name(frame) == "inventory"
    data = _event_data(frame)
    assert data["kind"] == "inventory_changed"
    count = db_session.scalar(select(func.count()).select_from(Document)) or 0
    # At least the row just registered is counted.
    assert count >= 1
    # Fingerprint is "<count>:<newest_uploaded_at or ''>".
    assert data["fingerprint"].startswith(f"{count}:")


def test_poll_inventory_pings_unchanged_then_signals_new_document(
    db_session: Session,
    seeded_users: dict[UserRole, User],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _redirect_session_scope(monkeypatch, db_session)
    _neutralise_sleep(monkeypatch)
    owner_id = seeded_users[UserRole.DATA_OWNER].id

    async def _drive() -> tuple[str, str, str]:
        gen = events._poll_inventory()
        try:
            first = await gen.__anext__()  # first poll -> inventory
            second = await gen.__anext__()  # unchanged -> ping
            documents_repo.register_document(
                db_session, uploaded_by=owner_id, filename="new.pdf"
            )
            db_session.flush()
            third = await gen.__anext__()  # +1 document -> inventory
            return first, second, third
        finally:
            await gen.aclose()

    first, second, third = asyncio.run(_drive())

    assert _event_name(first) == "inventory"

    # No inventory change between the first two polls -> heartbeat, not a signal.
    assert _event_name(second) == "ping"

    # Registering a document changes the fingerprint -> a fresh inventory frame
    # whose count is exactly one higher than the baseline.
    assert _event_name(third) == "inventory"
    assert _event_data(third)["fingerprint"] != _event_data(first)["fingerprint"]
    assert _fingerprint_count(third) == _fingerprint_count(first) + 1
