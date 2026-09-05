"""Engine and session management, :mod:`app.db.session`.

The behavior worth testing here is the refusals and the transaction boundaries,
not the happy path of opening a connection. Two claims in that module's docstrings
are load-bearing and are asserted rather than trusted: a missing ``DATABASE_URL``
fails loudly instead of falling back to a default, and ``session_scope`` rolls back
on any exception rather than leaving a half-written unit of work committed.

The tests that commit run against a scratch database, so nothing they write lands
in the shared development one.
"""

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.config import Settings, get_settings
from app.db import session as session_module
from app.db.enums import UserRole
from app.db.models import User
from app.db.repositories import identity
from app.db.session import (
    DATABASE_URL_ENV_VAR,
    DatabaseNotConfiguredError,
    require_database_url,
    session_scope,
)

# --------------------------------------------------------------------------
# Refusing to guess at a connection string
# --------------------------------------------------------------------------


def test_a_blank_database_url_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """Blank is treated as unset, not as a valid empty connection string."""
    monkeypatch.setenv(DATABASE_URL_ENV_VAR, "   ")
    get_settings.cache_clear()

    with pytest.raises(DatabaseNotConfiguredError):
        require_database_url()


def test_an_absent_database_url_is_refused(monkeypatch: pytest.MonkeyPatch) -> None:
    """No default connection string exists, deliberately.

    A fallback like ``postgresql+psycopg://localhost/qaegis`` would embed a
    credential in source and, worse, let a misconfigured process connect somewhere
    unintended and appear to work.
    """
    monkeypatch.setattr(
        session_module, "get_settings", lambda: Settings(database_url=None)
    )

    with pytest.raises(DatabaseNotConfiguredError):
        require_database_url()


def test_the_refusal_names_the_variable_to_set(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An error that does not say what to fix costs someone an afternoon."""
    monkeypatch.setattr(
        session_module, "get_settings", lambda: Settings(database_url=None)
    )

    with pytest.raises(DatabaseNotConfiguredError) as exc_info:
        require_database_url()

    message = str(exc_info.value)
    assert DATABASE_URL_ENV_VAR in message
    assert "docs/LOCAL_DEV.md" in message


def test_engines_are_reused_per_url(migrated_scratch_engine: Engine) -> None:
    """One engine per connection string, so its pool is actually shared.

    Keyed on the URL rather than held as a single global: the test suite swaps
    configuration between tests, and a single-slot cache would hand back an engine
    pointed at the previous database.
    """
    assert session_module.get_engine() is session_module.get_engine()


# --------------------------------------------------------------------------
# session_scope transaction boundaries
# --------------------------------------------------------------------------


def test_session_scope_commits_on_success(migrated_scratch_engine: Engine) -> None:
    """Work done inside the block is durable after it exits."""
    with session_scope() as session:
        identity.create_user(
            session,
            name="Committed User",
            email="committed@example.test",
            role=UserRole.AUDITOR,
        )

    with migrated_scratch_engine.connect() as connection:
        count = connection.execute(
            text("SELECT count(*) FROM users WHERE email = 'committed@example.test'")
        ).scalar_one()
    assert count == 1


def test_session_scope_rolls_back_on_failure(migrated_scratch_engine: Engine) -> None:
    """A raised exception discards the whole unit of work.

    This is what makes "the decision and its audit entry are atomic" true. If a
    failure left the earlier write committed, a classification could survive
    without the audit entry that ``PRD.md`` Section 7 requires.
    """
    with pytest.raises(RuntimeError, match="deliberate"):
        with session_scope() as session:
            identity.create_user(
                session,
                name="Doomed User",
                email="doomed@example.test",
                role=UserRole.AUDITOR,
            )
            raise RuntimeError("deliberate failure after a write")

    with migrated_scratch_engine.connect() as connection:
        count = connection.execute(
            text("SELECT count(*) FROM users WHERE email = 'doomed@example.test'")
        ).scalar_one()
    assert count == 0


def test_session_scope_re_raises_unchanged(migrated_scratch_engine: Engine) -> None:
    """The original exception reaches the caller, not a wrapped substitute.

    Swallowing or replacing it would let a caller believe a write succeeded.
    """
    sentinel = ValueError("the caller's own error")

    with pytest.raises(ValueError) as exc_info:
        with session_scope():
            raise sentinel

    assert exc_info.value is sentinel


# --------------------------------------------------------------------------
# The request-scoped dependency
# --------------------------------------------------------------------------


def test_get_db_session_yields_a_usable_session(
    migrated_scratch_engine: Engine,
) -> None:
    """The FastAPI dependency, exercised without the override the API tests use.

    Every other API test substitutes a session so its writes roll back, which
    means the real dependency would otherwise never run in the suite.
    """
    from app.api.deps import get_db_session

    generator = get_db_session()
    session = next(generator)
    assert isinstance(session, Session)
    identity.create_user(
        session,
        name="Dependency User",
        email="dependency@example.test",
        role=UserRole.ENGINEER,
    )

    # Driven to completion, not closed. ``generator.close()`` raises
    # ``GeneratorExit`` at the yield, which is an exception and so takes the
    # rollback branch. FastAPI signals a successful request by resuming the
    # generator until it stops, which is what commits, so that is what this
    # asserts against.
    with pytest.raises(StopIteration):
        next(generator)

    with session_scope() as verifying:
        assert (
            verifying.query(User)
            .filter(User.email == "dependency@example.test")
            .count()
            == 1
        )
