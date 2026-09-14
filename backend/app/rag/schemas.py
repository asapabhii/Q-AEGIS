"""Pydantic models for agentic RAG, ``SPEC.md`` 3.12."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class RagCitation(BaseModel):
    """One retrieved record the answer is grounded in."""

    model_config = ConfigDict(extra="forbid")

    chunk_id: UUID
    source_type: str
    source_id: str | None = None
    document_id: UUID | None = None
    content: str
    score: float


class RagAnswer(BaseModel):
    """Verified answer from the four-node RAG pipeline."""

    model_config = ConfigDict(extra="forbid")

    question: str
    answer: str
    verified: bool
    plan: str
    citations: list[RagCitation]
    embedding_model: str = Field(
        description="Always names the stub or real embedding implementation."
    )
    refusal_reason: str | None = None


class RagIngestResult(BaseModel):
    """How many chunks were written for a document."""

    model_config = ConfigDict(extra="forbid")

    document_id: UUID
    chunks_written: int
    embedding_model: str
