"""Neo4j driver factory for the knowledge graph, ``SPEC.md`` 3.11."""

from __future__ import annotations

from contextlib import contextmanager
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


@contextmanager
def neo4j_driver() -> Iterator[Any]:
    """Yield a Neo4j driver; close it on exit.

    Raises:
        GraphNotConfiguredError: when settings omit Neo4j.
        ImportError: when the ``neo4j`` package is not installed.
    """
    if not is_graph_configured():
        raise GraphNotConfiguredError(
            "Neo4j is not configured. Set QAEGIS_NEO4J_URI, QAEGIS_NEO4J_USER, "
            "and QAEGIS_NEO4J_PASSWORD (see .env.example)."
        )
    from neo4j import GraphDatabase

    settings = get_settings()
    driver = GraphDatabase.driver(
        settings.qaegis_neo4j_uri,  # type: ignore[arg-type]
        auth=(settings.qaegis_neo4j_user, settings.qaegis_neo4j_password),
    )
    try:
        yield driver
    finally:
        driver.close()
