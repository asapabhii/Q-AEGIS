"""Shared pytest fixtures.

The database-backed fixtures run against a real Postgres, never SQLite and never
a mock. The guarantees under test are a plpgsql trigger, a partial unique index,
``NULLS NOT DISTINCT``, and CHECK constraints; a stand-in would let every one of
those tests pass while the real database enforced nothing.

Each test runs inside a transaction that is rolled back afterwards, rather than
cleaning up by deleting rows. That is not a stylistic preference: ``audit_log``
rejects DELETE and TRUNCATE by design, so row-level cleanup is impossible there.
A rollback discards the savepoint without ever issuing a statement the triggers
would refuse.
"""

import os
from collections.abc import Iterator
from pathlib import Path
from typing import Any
from uuid import uuid4

import pytest
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL
from sqlalchemy.orm import Session

from app.api.deps import get_db_session
from app.config import get_settings
from app.db.enums import UserRole
from app.db.models import Document, User
from app.db.repositories import documents as documents_repo
from app.db.seed import dev_email, seed_development_users
from app.db.session import (
    DatabaseNotConfiguredError,
    _engine_for_url,
    require_database_url,
)
from app.main import create_app

# Required by ``seed_development_users``; never a production secret.
os.environ.setdefault("QAEGIS_DEV_SEED_PASSWORD", "local-dev-only-password")

#: Repository-relative path to the Alembic configuration.
BACKEND_ROOT = Path(__file__).resolve().parents[1]
ALEMBIC_INI = BACKEND_ROOT / "alembic.ini"


def alembic_config(url: str) -> Config:
    """Build an Alembic config pointed at ``url``.

    ``script_location`` is set to an absolute path rather than left as the
    relative value in ``alembic.ini``, so the tests pass regardless of the
    directory pytest was invoked from.
    """
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", url)
    return config


@pytest.fixture(autouse=True)
def _clear_settings_cache(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Reset the cached settings around every test.

    ``get_settings`` is ``lru_cache``d, so a test that changes the environment
    would otherwise leak its configuration into unrelated tests through the
    cached instance, and the resulting failure would depend on test ordering.
    """
    # Dummy master key so assessment encrypt paths work in API tests.
    monkeypatch.setenv(
        "CRYPTO_MASTER_KEY",
        "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA",
    )
    monkeypatch.setenv("RISK_RECOMPUTE_INTERVAL_SECONDS", "0")
    # Tests keep the forgeable role header as a DEV bypass; JWT still works
    # when a test issues a token against this secret.
    monkeypatch.setenv("JWT_SECRET", "test-only-jwt-secret-not-for-prod")
    monkeypatch.setenv("AUTH_DEV_HEADER_BYPASS", "true")
    monkeypatch.setenv("QAEGIS_DEV_SEED_PASSWORD", "local-dev-only-password")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture(scope="session")
def migrated_engine() -> Iterator[Engine]:
    """Bring the configured database to ``head`` and yield an engine for it.

    The schema under test is built by running the real migration, not by
    ``Base.metadata.create_all()``. Two reasons, both load-bearing: the triggers
    and the ``NULLS NOT DISTINCT`` constraint exist only in the migration, and a
    migration that works against the models but fails against an empty database
    should be caught here rather than by the next person to set up the project.
    """
    get_settings.cache_clear()
    try:
        url = require_database_url()
    except DatabaseNotConfiguredError as exc:
        # Fail rather than skip. A skipped database suite is a green run that
        # verified none of the guarantees this module exists to verify, and the
        # coverage gate would still pass.
        pytest.fail(f"{exc}\n\nThe database-backed tests cannot run without it.")

    command.upgrade(alembic_config(url), "head")
    engine = _engine_for_url(url)
    yield engine


@pytest.fixture
def scratch_url(migrated_engine: Engine) -> Iterator[str]:
    """Create an empty database, yield its URL, and drop it afterwards.

    Derived from the configured connection so it lands on the same server with the
    same credentials, rather than needing separate configuration. Used by tests
    that have to migrate, tear down, or commit against a database without
    disturbing the one every other test shares.
    """
    base: URL = migrated_engine.url
    name = f"qaegis_scratch_{uuid4().hex[:12]}"

    # CREATE DATABASE cannot run inside a transaction block, hence AUTOCOMMIT.
    # "postgres" is the maintenance database, connected to only for these two
    # statements.
    admin = create_engine(
        base.set(database="postgres"), isolation_level="AUTOCOMMIT", future=True
    )
    try:
        with admin.connect() as connection:
            connection.execute(text(f'CREATE DATABASE "{name}"'))
        yield base.set(database=name).render_as_string(hide_password=False)
    finally:
        with admin.connect() as connection:
            # WITH (FORCE) terminates any connection still open against it. A
            # leaked connection would otherwise leave the scratch database behind
            # and make the next run's teardown noisier than the failure it is
            # reporting.
            connection.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


@pytest.fixture
def scratch_engine(
    scratch_url: str, monkeypatch: pytest.MonkeyPatch
) -> Iterator[Engine]:
    """Point ``DATABASE_URL`` at the scratch database and yield an engine for it.

    The environment is what changes, not the Alembic config: ``env.py`` reads the
    URL from :mod:`app.config` on purpose, so there is exactly one source of truth
    for which database a migration runs against. Overriding it through the
    environment exercises that path rather than bypassing it.
    """
    monkeypatch.setenv("DATABASE_URL", scratch_url)
    get_settings.cache_clear()

    engine = create_engine(scratch_url, future=True)
    try:
        yield engine
    finally:
        engine.dispose()


@pytest.fixture
def migrated_scratch_engine(scratch_engine: Engine) -> Engine:
    """A scratch database with the schema applied, safe to commit against."""
    command.upgrade(alembic_config(str(scratch_engine.url)), "head")
    return scratch_engine


@pytest.fixture
def db_session(migrated_engine: Engine) -> Iterator[Session]:
    """A session inside a transaction that is always rolled back.

    ``join_transaction_mode="create_savepoint"`` is what makes this work with code
    that commits: application code under test calls ``commit()`` normally, which
    releases a savepoint rather than ending the outer transaction, so the rollback
    below still discards everything the test wrote.
    """
    connection = migrated_engine.connect()
    transaction = connection.begin()
    session = Session(
        bind=connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()


@pytest.fixture
def seeded_users(db_session: Session) -> dict[UserRole, User]:
    """Seed one development user per role and return them by role.

    Needed by anything that writes a row referencing ``users.id``, which is most
    of the schema. See :mod:`app.db.seed` for why these accounts exist at all.
    """
    seed_development_users(db_session)
    return {
        role: db_session.query(User).filter(User.email == dev_email(role)).one()
        for role in UserRole
    }


@pytest.fixture
def registered_document(
    db_session: Session, seeded_users: dict[UserRole, User]
) -> Document:
    """A document registered by the seeded Data Owner."""
    return documents_repo.register_document(
        db_session,
        uploaded_by=seeded_users[UserRole.DATA_OWNER].id,
        filename="quarterly-report.pdf",
    )


def _build_client(session: Session) -> Iterator[TestClient]:
    """Yield a client whose requests run in ``session``, one savepoint each."""
    application = create_app()

    def override() -> Iterator[Session]:
        # Mirrors the per-request transaction in app.api.deps.get_db_session,
        # scaled down to a savepoint inside the test's transaction. Without the
        # rollback branch, a test asserting that a failed request leaves nothing
        # behind would pass for the wrong reason.
        nested = session.begin_nested()
        try:
            yield session
            nested.commit()
        except Exception:
            nested.rollback()
            raise

    application.dependency_overrides[get_db_session] = override
    try:
        with TestClient(application) as test_client:
            yield test_client
    finally:
        application.dependency_overrides.clear()


@pytest.fixture
def client(
    db_session: Session, seeded_users: dict[UserRole, User]
) -> Iterator[TestClient]:
    """A test client over a fresh application, with users seeded."""
    yield from _build_client(db_session)


@pytest.fixture
def unseeded_client(db_session: Session) -> Iterator[TestClient]:
    """A test client with no users seeded.

    Exercises the deliberate refusal in
    :func:`app.api.deps.resolve_seeded_actor`: with no user holding the claimed
    role, a request cannot be attributed to an actor and must fail rather than
    quietly inventing one.
    """
    yield from _build_client(db_session)


@pytest.fixture
def raising_client(
    db_session: Session, seeded_users: dict[UserRole, User]
) -> Iterator[TestClient]:
    """A client that converts an unhandled server error into a 500 response.

    ``TestClient`` re-raises server exceptions by default, which is usually what
    you want. Here it gets in the way of asserting that a failed request rolled
    its writes back, since the assertion has to run after the response.
    """
    application = create_app()

    def override() -> Iterator[Session]:
        nested = db_session.begin_nested()
        try:
            yield db_session
            nested.commit()
        except Exception:
            nested.rollback()
            raise

    application.dependency_overrides[get_db_session] = override
    try:
        with TestClient(application, raise_server_exceptions=False) as test_client:
            yield test_client
    finally:
        application.dependency_overrides.clear()


def count_rows(session: Session, model: Any) -> int:
    """Return the number of rows currently visible for ``model``."""
    return session.query(model).count()
