"""Knowledge graph, ``SPEC.md`` 3.11, implements ``PRD.md`` FR-10.

Neo4j stores employees, repositories, vendors, cloud assets, and documents as
nodes with multi-hop relationships. Attack-path queries are Cypher, not SQL
joins. Application-level links use ``documents.id`` as a property; there is no
FK into Postgres (see ``docs/data-dictionary.md``).

Owner: Abhinav (``WORK_DIVISION.md``).
"""

from app.graph.client import (
    GraphNotConfiguredError,
    is_graph_configured,
    neo4j_driver,
)
from app.graph.paths import find_attack_paths, find_document_paths
from app.graph.seed import seed_demo_graph

__all__ = [
    "GraphNotConfiguredError",
    "find_attack_paths",
    "find_document_paths",
    "is_graph_configured",
    "neo4j_driver",
    "seed_demo_graph",
]
