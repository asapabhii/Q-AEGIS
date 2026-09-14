"""Crypto-shredding endpoint, ``SPEC.md`` 3.9, ``PRD.md`` FR-8.

SECURITY CAVEAT: liboqs is NOT independently audited.
"""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import DbSession, ShredCaller, resolve_seeded_actor
from app.crypto.shred import shred_audit_payload, shred_document_keys
from app.db.enums import AuditEventType, DocumentStatus
from app.db.repositories import audit as audit_repo
from app.db.repositories import documents as documents_repo

router = APIRouter(tags=["shred"])


class ShredRequest(BaseModel):
    """Confirm irreversible key destruction for one document."""

    model_config = ConfigDict(extra="forbid")

    document_id: UUID
    confirmed: bool = Field(
        description="Must be true. Soft confirmation; no undo after success."
    )


class ShredResponse(BaseModel):
    """Outcome of one shredding request."""

    model_config = ConfigDict(extra="forbid")

    document_id: UUID
    ciphertext_count: int
    newly_destroyed: int
    already_shredded: bool
    irreversible: bool = True


@router.post(
    "/shred",
    response_model=ShredResponse,
    status_code=status.HTTP_200_OK,
    summary="Destroy encryption keys for a document (crypto-shredding)",
)
def shred_document(
    request: ShredRequest,
    session: DbSession,
    caller: ShredCaller,
) -> ShredResponse:
    """Overwrite wrapped DEKs so ciphertext becomes permanently unreadable.

    Audit rows are never deleted. Ciphertext bytes remain as evidence. Calling
    again on an already-shredded document is idempotent and still audited.

    SECURITY CAVEAT: liboqs is NOT independently audited.
    """
    if not request.confirmed:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "confirmed must be true. Key destruction is irreversible; "
                "the API refuses an unconfirmed request."
            ),
        )

    document = documents_repo.get_document(session, request.document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No document registered with id {request.document_id}.",
        )

    rows, newly_destroyed = shred_document_keys(session, document.id)
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "No ciphertext is stored for this document. Encrypt it first "
                "via POST /api/v1/assessments with content, then shred."
            ),
        )

    if document.current_status != DocumentStatus.ARCHIVED:
        document.current_status = DocumentStatus.ARCHIVED
        session.flush()

    actor = resolve_seeded_actor(session, caller)
    audit_repo.append_entry(
        session,
        event_type=AuditEventType.CRYPTO_SHREDDED.value,
        document_id=document.id,
        actor_id=actor.id,
        payload=shred_audit_payload(
            document_id=document.id,
            ciphertext_ids=[row.id for row in rows],
            keys_destroyed=len(rows),
            newly_destroyed=newly_destroyed,
        ),
    )

    return ShredResponse(
        document_id=document.id,
        ciphertext_count=len(rows),
        newly_destroyed=newly_destroyed,
        already_shredded=newly_destroyed == 0,
        irreversible=True,
    )
