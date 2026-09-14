"""Multi-hop attack-path queries over Neo4j, ``SPEC.md`` 3.11 / PRD FR-10."""

from __future__ import annotations

from uuid import UUID

from app.graph.client import neo4j_driver
from app.graph.schemas import AttackPathResponse, GraphNode, GraphPath
from app.graph.seed import _node_from_neo4j


def find_document_paths(document_id: UUID, *, max_hops: int = 4) -> AttackPathResponse:
    """Return paths that touch the document and surface related attack edges.

    Finds paths of length 1..``max_hops`` from the Document node to any
    Employee / Repository / Vendor / CloudAsset, which surfaces relationships
    invisible from a single audit event in isolation.
    """
    if max_hops < 1 or max_hops > 6:
        raise ValueError("max_hops must be between 1 and 6")

    doc_key = str(document_id)
    cypher = f"""
    MATCH path = (d:Document {{key: $doc_key}})-[*1..{max_hops}]-(other)
    WHERE other:Employee OR other:Repository OR other:Vendor OR other:CloudAsset
    RETURN path
    LIMIT 25
    """
    paths: list[GraphPath] = []
    with neo4j_driver() as driver:
        with driver.session() as session:
            result = session.run(cypher, doc_key=doc_key)
            for record in result:
                path = record["path"]
                nodes = [_node_from_neo4j(n) for n in path.nodes]
                rels = [rel.type for rel in path.relationships]
                if len(nodes) < 2 or not rels:
                    continue
                summary = " → ".join(f"{n['labels'][0]}({n['key']})" for n in nodes)
                paths.append(
                    GraphPath(
                        hops=len(rels),
                        nodes=[GraphNode.model_validate(n) for n in nodes],
                        relationships=rels,
                        summary=summary,
                    )
                )

    note = None
    if not paths:
        note = (
            "No paths found for this document. Seed the demo graph with "
            "POST /api/v1/graph/seed (optionally pass this document_id)."
        )
    return AttackPathResponse(document_id=document_id, paths=paths, note=note)


def find_attack_paths(
    *,
    start_key: str,
    start_label: str,
    end_label: str | None = None,
    max_hops: int = 4,
) -> AttackPathResponse:
    """Generic multi-hop search from a start node toward optional end labels."""
    if max_hops < 1 or max_hops > 6:
        raise ValueError("max_hops must be between 1 and 6")
    allowed = {"Employee", "Document", "Repository", "Vendor", "CloudAsset"}
    if start_label not in allowed:
        raise ValueError(f"start_label must be one of {sorted(allowed)}")
    if end_label is not None and end_label not in allowed:
        raise ValueError(f"end_label must be one of {sorted(allowed)}")

    end_filter = (
        f"AND end:{end_label}"
        if end_label
        else "AND (end:Employee OR end:Repository OR end:Vendor OR end:CloudAsset "
        "OR end:Document)"
    )
    cypher = f"""
    MATCH path = (start:{start_label} {{key: $start_key}})-[*1..{max_hops}]-(end)
    WHERE start <> end {end_filter}
    RETURN path
    LIMIT 25
    """
    paths: list[GraphPath] = []
    with neo4j_driver() as driver:
        with driver.session() as session:
            result = session.run(cypher, start_key=start_key)
            for record in result:
                path = record["path"]
                nodes = [_node_from_neo4j(n) for n in path.nodes]
                rels = [rel.type for rel in path.relationships]
                if len(nodes) < 2 or not rels:
                    continue
                summary = " → ".join(f"{n['labels'][0]}({n['key']})" for n in nodes)
                paths.append(
                    GraphPath(
                        hops=len(rels),
                        nodes=[GraphNode.model_validate(n) for n in nodes],
                        relationships=rels,
                        summary=summary,
                    )
                )
    return AttackPathResponse(document_id=None, paths=paths, note=None)
