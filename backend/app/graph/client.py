"""Neo4j driver factory for the knowledge graph, ``SPEC.md`` 3.11."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

from app.config import get_settings


class GraphNotConfiguredError(RuntimeError):
    """Raised when Neo4j URI/credentials are missing."""


def is_graph_configured() -> bool:
    """True when ``QAEGIS_NEO4J_URI`` (and auth) are set."""
    settings = get_settings()
    return bool(
        settings.qaegis_neo4j_uri
        and settings.qaegis_neo4j_user
        and settings.qaegis_neo4j_password
    )


def _uri_and_driver_kwargs() -> tuple[str, dict[str, Any]]:
    """Return ``(uri, kwargs)`` for ``GraphDatabase.driver``.

    The Neo4j Python driver forbids ``trusted_certificates`` on ``bolt+s://``
    / ``neo4j+s://`` URIs (encryption is implied by the scheme and trusts the
    system store). Local compose uses a private CA, so when
    ``QAEGIS_NEO4J_SSL_CA_CERTS`` is set we rewrite to ``bolt://`` /
    ``neo4j://`` and pass ``encrypted=True`` plus ``TrustCustomCAs``.
    """
    settings = get_settings()
    uri = settings.qaegis_neo4j_uri
    if not uri:
        raise GraphNotConfiguredError("QAEGIS_NEO4J_URI is not set.")

    kwargs: dict[str, Any] = {
        "auth": (settings.qaegis_neo4j_user, settings.qaegis_neo4j_password),
    }
    ca_path = settings.qaegis_neo4j_ssl_ca_certs
    if ca_path:
        resolved = Path(ca_path).expanduser()
        if not resolved.is_file():
            raise GraphNotConfiguredError(
                f"QAEGIS_NEO4J_SSL_CA_CERTS points to a missing file: {ca_path}"
            )
        from neo4j import TrustCustomCAs

        if uri.startswith("bolt+s://"):
            uri = "bolt://" + uri.removeprefix("bolt+s://")
        elif uri.startswith("neo4j+s://"):
            uri = "neo4j://" + uri.removeprefix("neo4j+s://")
        kwargs["encrypted"] = True
        kwargs["trusted_certificates"] = TrustCustomCAs(str(resolved.resolve()))
    return uri, kwargs


@contextmanager
def neo4j_driver() -> Iterator[Any]:
    """Yield a Neo4j driver; close it on exit.

    Raises:
        GraphNotConfiguredError: when settings omit Neo4j or the CA path is bad.
        ImportError: when the ``neo4j`` package is not installed.
    """
    if not is_graph_configured():
        raise GraphNotConfiguredError(
            "Neo4j is not configured. Set QAEGIS_NEO4J_URI, QAEGIS_NEO4J_USER, "
            "and QAEGIS_NEO4J_PASSWORD (see .env.example)."
        )
    from neo4j import GraphDatabase

    uri, kwargs = _uri_and_driver_kwargs()
    driver = GraphDatabase.driver(uri, **kwargs)
    try:
        yield driver
    finally:
        driver.close()
