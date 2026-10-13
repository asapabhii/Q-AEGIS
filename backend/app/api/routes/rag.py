"""Agentic RAG HTTP API, ``SPEC.md`` 3.12 / ``PRD.md`` FR-11."""

from __future__ import annotations

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import DbSession, RagCaller, resolve_seeded_actor
from app.db.enums import AuditEventType
from app.db.repositories import audit as audit_repo
from app.db.repositories import documents as documents_repo
from app.rag.ingest import ingest_document_records
from app.rag.pipeline import ask_question
from app.rag.schemas import RagAnswer, RagIngestResult

router = APIRouter(tags=["rag"])


class RagAskRequest(BaseModel):
    """Natural-language question about system records."""

    model_config = ConfigDict(extra="forbid")

    question: str = Field(min_length=3, max_length=2000)
    document_id: UUID | None = None


@router.post(
    "/rag/ingest/{document_id}",
    response_model=RagIngestResult,
    status_code=status.HTTP_201_CREATED,
    summary="Index inventory + audit records for RAG retrieval",
)
def ingest_document(
    document_id: UUID,
    session: DbSession,
    caller: RagCaller,
) -> RagIngestResult:
    """Build pgvector chunks from real decision records for one document."""
    actor = resolve_seeded_actor(session, caller)
    if documents_repo.get_document(session, document_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found.",
        )
    try:
        result = ingest_document_records(session, document_id)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RAG ingest failed: {exc}",
        ) from exc
    audit_repo.append_entry(
        session,
        event_type=AuditEventType.RAG_INGESTED.value,
        actor_id=actor.id,
        document_id=document_id,
        payload={
            "chunks_written": result.chunks_written,
            "embedding_model": result.embedding_model,
        },
    )
    return result


@router.post(
    "/rag/ask",
    response_model=RagAnswer,
    summary="Ask a grounded question (Planner→Retriever→Reasoner→Verifier)",
)
def rag_ask(
    request: RagAskRequest,
    session: DbSession,
    caller: RagCaller,
) -> RagAnswer:
    """Answer only when the Verifier can ground the draft in retrieved records."""
    actor = resolve_seeded_actor(session, caller)
    if request.document_id is not None:
        if documents_repo.get_document(session, request.document_id) is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Document not found.",
            )
    try:
        answer = ask_question(
            session,
            question=request.question,
            document_id=request.document_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"RAG ask failed: {exc}",
        ) from exc

    audit_repo.append_entry(
        session,
        event_type=AuditEventType.RAG_ANSWERED.value,
        actor_id=actor.id,
        document_id=request.document_id,
        payload={
            "question": answer.question,
            "verified": answer.verified,
            "citation_count": len(answer.citations),
            "embedding_model": answer.embedding_model,
            "refused": answer.refusal_reason is not None,
        },
    )
    return answer
