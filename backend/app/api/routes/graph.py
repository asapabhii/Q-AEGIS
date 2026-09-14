"""Knowledge-graph HTTP API, ``SPEC.md`` 3.11 / ``PRD.md`` FR-10."""

from __future__ import annotations

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, ConfigDict

from app.api.deps import DbSession, GraphCaller, resolve_seeded_actor
from app.db.enums import AuditEventType
from app.db.repositories import audit as audit_repo
from app.db.repositories import documents as documents_repo
from app.graph.client import GraphNotConfiguredError, is_graph_configured
from app.graph.paths import find_attack_paths, find_document_paths
from app.graph.schemas import AttackPathResponse, GraphSeedResponse
from app.graph.seed import seed_demo_graph

router = APIRouter(tags=["graph"])


class GraphSeedRequest(BaseModel):
    """Optionally bind the demo graph to a real document id."""

    model_config = ConfigDict(extra="forbid")

    document_id: UUID | None = None


@router.get(
    "/graph/status",
    summary="Whether Neo4j is configured for FR-10 queries",
)
def graph_status() -> dict[str, bool]:
    """Liveness helper; does not require auth (same idea as health)."""
    return {"configured": is_graph_configured()}


@router.post(
    "/graph/seed",
    response_model=GraphSeedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upsert the demo attack-path graph into Neo4j",
)
def seed_graph(
    request: GraphSeedRequest,
    session: DbSession,
    caller: GraphCaller,
) -> GraphSeedResponse:
    """Load the synthetic multi-hop demo (and optionally link a document)."""
    actor = resolve_seeded_actor(session, caller)
    if request.document_id is not None:
        doc = documents_repo.get_document(session, request.document_id)
        if doc is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found.",
            )
    try:
        counts = seed_demo_graph(document_id=request.document_id)
    except GraphNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Neo4j seed failed: {exc}",
        ) from exc

    audit_repo.append_entry(
        session,
        event_type=AuditEventType.GRAPH_SEEDED.value,
        actor_id=actor.id,
        document_id=request.document_id,
        payload={
            "action": "graph.seed",
            "nodes_upserted": counts["nodes_upserted"],
            "relationships_upserted": counts["relationships_upserted"],
        },
    )
    return GraphSeedResponse(
        nodes_upserted=counts["nodes_upserted"],
        relationships_upserted=counts["relationships_upserted"],
    )


@router.get(
    "/graph/documents/{document_id}/paths",
    response_model=AttackPathResponse,
    summary="Multi-hop attack paths touching one document",
)
def document_attack_paths(
    document_id: UUID,
    session: DbSession,
    caller: GraphCaller,
    max_hops: Annotated[int, Query(ge=1, le=6)] = 4,
) -> AttackPathResponse:
    """Surface relationships not visible from a single event in isolation."""
    resolve_seeded_actor(session, caller)
    doc = documents_repo.get_document(session, document_id)
    if doc is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )
    try:
        return find_document_paths(document_id, max_hops=max_hops)
    except GraphNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Neo4j query failed: {exc}",
        ) from exc


@router.get(
    "/graph/attack-paths",
    response_model=AttackPathResponse,
    summary="Multi-hop paths from a named start node",
)
def attack_paths(
    session: DbSession,
    caller: GraphCaller,
    start_key: Annotated[str, Query(min_length=1, max_length=200)],
    start_label: Annotated[
        str,
        Query(description="Employee | Document | Repository | Vendor | CloudAsset"),
    ],
    end_label: Annotated[str | None, Query()] = None,
    max_hops: Annotated[int, Query(ge=1, le=6)] = 4,
) -> AttackPathResponse:
    """Generic Cypher multi-hop search for analyst exploration."""
    resolve_seeded_actor(session, caller)
    try:
        return find_attack_paths(
            start_key=start_key.strip(),
            start_label=start_label.strip(),
            end_label=end_label.strip() if end_label else None,
            max_hops=max_hops,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(exc),
        ) from exc
    except GraphNotConfiguredError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Neo4j query failed: {exc}",
        ) from exc
