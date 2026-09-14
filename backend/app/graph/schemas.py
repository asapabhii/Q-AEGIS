"""Pydantic models for knowledge-graph API responses, ``SPEC.md`` 3.11."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class GraphNode(BaseModel):
    """One node on an attack path."""

    model_config = ConfigDict(extra="forbid")

    labels: list[str] = Field(min_length=1)
    key: str = Field(min_length=1, description="Stable id property for the node.")
    properties: dict[str, Any] = Field(default_factory=dict)


class GraphPath(BaseModel):
    """One multi-hop path (nodes in order, relationships between them)."""

    model_config = ConfigDict(extra="forbid")

    hops: int = Field(ge=1)
    nodes: list[GraphNode] = Field(min_length=2)
    relationships: list[str] = Field(min_length=1)
    summary: str = Field(min_length=1)


class AttackPathResponse(BaseModel):
    """Attack paths returned for a query."""

    model_config = ConfigDict(extra="forbid")

    document_id: UUID | None = None
    paths: list[GraphPath]
    note: str | None = None


class GraphSeedResponse(BaseModel):
    """Result of seeding the demo attack-path graph."""

    model_config = ConfigDict(extra="forbid")

    nodes_upserted: int
    relationships_upserted: int
    demo: bool = True
