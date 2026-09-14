"""Seed a local demo attack-path graph into Neo4j, ``SPEC.md`` 3.11.

The graph is synthetic and labelled as a demo. It exists so multi-hop queries
have something to traverse without live third-party connectors (PRD NG3).
"""

from __future__ import annotations

from typing import Any
from uuid import UUID

from app.graph.client import neo4j_driver


def seed_demo_graph(*, document_id: UUID | None = None) -> dict[str, int]:
    """Upsert a fixed demo topology; optionally attach one real document id.

    Topology (attack-relevant hops):
    Employee -[OWNS]-> Document -[STORED_ON]-> CloudAsset
    Employee -[COMMITS_TO]-> Repository -[DEPENDS_ON]-> Vendor -[HOSTS_ON]-> CloudAsset
    Employee -[ACCESSES]-> CloudAsset
    """
    doc_key = str(document_id) if document_id is not None else "demo-document-001"
    nodes = 0
    rels = 0

    with neo4j_driver() as driver:
        with driver.session() as session:
            session.run(
                """
                MERGE (e:Employee {key: $emp_key})
                SET e.name = $emp_name, e.email = $emp_email
                MERGE (d:Document {key: $doc_key})
                SET d.document_id = $doc_key, d.title = $doc_title
                MERGE (r:Repository {key: $repo_key})
                SET r.name = $repo_name
                MERGE (v:Vendor {key: $vendor_key})
                SET v.name = $vendor_name
                MERGE (c:CloudAsset {key: $cloud_key})
                SET c.name = $cloud_name, c.provider = $cloud_provider
                """,
                emp_key="emp-alice",
                emp_name="Alice Chen",
                emp_email="alice@dev.qaegis.local",
                doc_key=doc_key,
                doc_title="Quarterly risk pack",
                repo_key="repo-payments",
                repo_name="payments-service",
                vendor_key="vendor-acme",
                vendor_name="Acme Cloud Integrator",
                cloud_key="cloud-s3-risk",
                cloud_name="s3://qaegis-risk-bucket",
                cloud_provider="aws",
            )
            nodes = 5
            result = session.run(
                """
                MATCH (e:Employee {key: $emp_key})
                MATCH (d:Document {key: $doc_key})
                MATCH (r:Repository {key: $repo_key})
                MATCH (v:Vendor {key: $vendor_key})
                MATCH (c:CloudAsset {key: $cloud_key})
                MERGE (e)-[:OWNS]->(d)
                MERGE (d)-[:STORED_ON]->(c)
                MERGE (e)-[:COMMITS_TO]->(r)
                MERGE (r)-[:DEPENDS_ON]->(v)
                MERGE (v)-[:HOSTS_ON]->(c)
                MERGE (e)-[:ACCESSES]->(c)
                RETURN 6 AS rel_count
                """,
                emp_key="emp-alice",
                doc_key=doc_key,
                repo_key="repo-payments",
                vendor_key="vendor-acme",
                cloud_key="cloud-s3-risk",
            )
            record = result.single()
            rels = int(record["rel_count"]) if record else 6

    return {"nodes_upserted": nodes, "relationships_upserted": rels}


def _node_from_neo4j(node: Any) -> dict[str, Any]:
    props = dict(node)
    key = str(props.get("key") or props.get("document_id") or node.element_id)
    return {
        "labels": list(node.labels),
        "key": key,
        "properties": {k: _jsonable(v) for k, v in props.items()},
    }


def _jsonable(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)
