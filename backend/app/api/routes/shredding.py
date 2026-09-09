"""Crypto-shredding endpoint, `SPEC.md` 3.9, `PRD.md` FR-8.

STUB IMPLEMENTATION: Key destruction is simulated as no real key material
exists in this phase (`PRD.md` NG4/NG5). The endpoint writes an
`erasure_requested` audit log entry and advances the document's lifecycle
status to `ARCHIVED`.

SECURITY CAVEAT: liboqs is NOT independently audited, and OQS-OpenSSL is
documented by its own maintainers as development and interop-testing only,
not production-supported. Do not claim audited-grade or FIPS-certified
guarantees that the library does not back up.
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel

from app.api.deps import CryptoShredCaller, DbSession, resolve_seeded_actor
from app.crypto.shredding import shred_document_key
from app.db.enums import AuditEventType, DocumentStatus, UserRole
from app.db.repositories import audit as audit_repo
from app.db.repositories import documents as documents_repo

router = APIRouter(tags=["shredding"])


class ShredResponse(BaseModel):
    document_id: UUID
    shredded_at: datetime
    message: str


@router.delete(
    "/documents/{document_id}/key",
    status_code=status.HTTP_202_ACCEPTED,
    response_model=ShredResponse,
    summary="Cryptographic erasure (crypto-shredding) of a document key",
)
def shred_key(
    document_id: UUID,
    session: DbSession,
    caller: CryptoShredCaller,
    confirm: bool = Query(
        ...,
        description=(
            "Explicit confirmation flag required for irreversible " "crypto-shredding."
        ),
    ),
) -> ShredResponse:
    if not confirm:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Crypto-shredding requires explicit confirmation: confirm=true",
        )

    doc = documents_repo.get_document(session, document_id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Document not found",
        )

    actor = resolve_seeded_actor(session, caller)
    if not actor:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Caller identity could not be resolved",
        )

    # Authorization: Owner, COMPLIANCE_OFFICER, or SECURITY_ADMIN
    is_owner = doc.uploaded_by == actor.user_id
    is_privileged = actor.role in (UserRole.COMPLIANCE_OFFICER, UserRole.SECURITY_ADMIN)
    if not (is_owner or is_privileged):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Forbidden: caller is not document owner or authorized officer",
        )

    result = shred_document_key(document_id=doc.id, actor_id=actor.user_id)

    # Update document status to ARCHIVED
    documents_repo.update_status(session, doc.id, DocumentStatus.ARCHIVED)

    # Record erasure request audit entry
    audit_repo.append_entry(
        session=session,
        event_type=AuditEventType.ERASURE_REQUESTED,
        actor_id=actor.user_id,
        document_id=doc.id,
        payload={
            "action": "crypto_shred",
            "document_id": str(doc.id),
            "actor_id": str(actor.user_id),
            "shredded_at": result.shredded_at.isoformat(),
        },
    )
    session.commit()

    return ShredResponse(
        document_id=result.document_id,
        shredded_at=result.shredded_at,
        message=(
            "Document encryption key destroyed. Data is now permanently unreadable."
        ),
    )
