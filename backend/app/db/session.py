"""Engine and session management for the relational store.

Nothing here connects at import time. The engine is built on first use, so
importing the application, serving the liveness endpoint, or running the
classifier all work with no database reachable, which is what lets the Docker
image's smoke test in CI start the container without Postgres.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings

#: Name of the environment variable carrying the connection string. Named in the
#: error below so a misconfigured environment says what to set.
DATABASE_URL_ENV_VAR = "DATABASE_URL"


class DatabaseNotConfiguredError(RuntimeError):
    """Raised when a code path needs the database and none is configured.

    A distinct type rather than a bare ``RuntimeError`` so a caller that can
    legitimately degrade (a readiness probe reporting "no database", say) can
    catch this without also swallowing unrelated runtime failures.
    """


def require_database_url() -> str:
    """Return the configured connection string, or fail loudly.

    Raises:
        DatabaseNotConfiguredError: when ``DATABASE_URL`` is unset or blank.
            Deliberately loud. The alternative, defaulting to a local database,
            risks a misconfigured process connecting somewhere unintended and
            appearing to work, which is worse than not starting.
    """
    url = get_settings().database_url
    if url is None or not url.strip():
        raise DatabaseNotConfiguredError(
            f"{DATABASE_URL_ENV_VAR} is not set. This code path requires the "
            "database (SPEC.md Section 5). Copy .env.example to .env and set it, "
            "and start the local stack with `cd infra && docker compose up -d`. "
            "See docs/LOCAL_DEV.md."
        )
    return url


@lru_cache(maxsize=None)
def _engine_for_url(url: str) -> Engine:
    """Build (and memoise) an engine for one connection string.

    Keyed on the URL rather than cached as a single global, because the test
    suite clears the settings cache to swap configuration between tests. A
    single-slot cache would hand back an engine pointed at the previous
    database.
    """
    return create_engine(
        url,
        # Verify a pooled connection before handing it out. Without this, a
        # connection dropped by a restarted Postgres container surfaces as a
        # confusing failure on the next unrelated request.
        pool_pre_ping=True,
        future=True,
    )


def get_engine() -> Engine:
    """Return the engine for the configured database."""
    return _engine_for_url(require_database_url())


def get_sessionmaker() -> sessionmaker[Session]:
    """Return a session factory bound to the configured engine.

    ``expire_on_commit`` is left off so a freshly committed object's attributes
    remain readable without another round trip. That matters here specifically:
    the classify endpoint commits and then serialises the row it just wrote.
    """
    return sessionmaker(bind=get_engine(), expire_on_commit=False, future=True)


@contextmanager
def session_scope() -> Iterator[Session]:
    """Run a unit of work in one transaction, committing or rolling back.

    Used by scripts and by anything outside the request cycle. Request handlers
    use the FastAPI dependency in :mod:`app.api.deps` instead, which is the same
    contract expressed as a dependency so tests can substitute a session.
    """
    session = get_sessionmaker()()
    try:
        yield session
        session.commit()
    except Exception:
        # Roll back and re-raise unchanged. Swallowing here would let a caller
        # believe a write succeeded, and for the audit log in particular a
        # silently dropped write is the failure mode PRD.md Section 7 calls a
        # defect.
        session.rollback()
        raise
    finally:
        session.close()
