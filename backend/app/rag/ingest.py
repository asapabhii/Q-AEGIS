"""Ingest Postgres decision records into pgvector for RAG grounding."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from app.db.repositories import audit as audit_repo
from app.db.repositories import documents as documents_repo
from app.db.repositories import inventory as inventory_repo
from app.rag.embeddings import embedding_model_name
from app.rag.schemas import RagIngestResult
from app.rag.store import delete_chunks_for_document, upsert_chunk


def ingest_document_records(session: Session, document_id: UUID) -> RagIngestResult:
    """Chunk audit trail + inventory snapshot text for one document.

    Replaces prior chunks for that document so re-ingest stays idempotent.
    """
    doc = documents_repo.get_document(session, document_id)
    if doc is None:
        raise LookupError(f"document {document_id} not found")

    delete_chunks_for_document(session, document_id)
    written = 0

    snap = inventory_repo.get_snapshot(session, document_id)
    if snap is not None:
        risk_value = snap.risk.risk_value if snap.risk else None
        consensus = snap.trust.consensus_value if snap.trust else None
        final_decision = snap.decision.final_decision if snap.decision else None
        profile_type = snap.profile.profile_type if snap.profile else None
        lines = [
            f"Document {snap.document.id} filename={snap.document.filename}",
            f"status={snap.document.current_status}",
            f"sensitivity={snap.sensitivity_label} source={snap.label_source}",
            f"risk={risk_value} trust={consensus}",
            f"policy={final_decision} crypto={profile_type}",
        ]
        upsert_chunk(
            session,
            document_id=document_id,
            source_type="inventory_snapshot",
            source_id=str(snap.document.id),
            content="\n".join(str(part) for part in lines),
            metadata={"kind": "inventory"},
        )
        written += 1

    entries = audit_repo.load_chain(session, document_id)
    for entry in entries:
        payload = entry.payload if isinstance(entry.payload, dict) else {}
        content = (
            f"audit event_type={entry.event_type} at={entry.created_at.isoformat()} "
            f"payload={payload}"
        )
        upsert_chunk(
            session,
            document_id=document_id,
            source_type="audit_entry",
            source_id=str(entry.id),
            content=content[:4000],
            metadata={"event_type": entry.event_type},
        )
        written += 1

    return RagIngestResult(
        document_id=document_id,
        chunks_written=written,
        embedding_model=embedding_model_name(),
    )
