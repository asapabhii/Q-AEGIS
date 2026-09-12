"""Crypto-profile selection endpoint, ``SPEC.md`` 3.7, ``PRD.md`` FR-6.

SECURITY CAVEAT: liboqs is NOT independently audited, and OQS-OpenSSL is
documented by its own maintainers as development and interop-testing only, not
production-supported. Do not claim audited-grade or FIPS-certified guarantees
that the library does not back up. This endpoint persists a profile choice; it
does not encrypt or decrypt bytes.
"""

from decimal import Decimal
from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.deps import (
    CryptoProfileCaller,
    DbSession,
    ShredDocumentCaller,
    resolve_seeded_actor,
)
from app.crypto.schemas import (
    CryptoProfileRequest,
    CryptoProfileResponse,
    CryptoShredRequest,
    CryptoShredResponse,
)
from app.crypto.selector import select_crypto_profile
from app.db.enums import AuditEventType, DocumentStatus
from app.db.repositories import audit as audit_repo
from app.db.repositories import crypto as crypto_repo
from app.db.repositories import documents as documents_repo
from app.db.repositories import policy as policy_repo
from app.db.repositories import trust as trust_repo

router = APIRouter(tags=["crypto"])


@router.post(
    "/crypto-profiles",
    response_model=CryptoProfileResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Select a protection profile from a persisted trust score",
)
def select_profile(
    request: CryptoProfileRequest,
    session: DbSession,
    caller: CryptoProfileCaller,
) -> CryptoProfileResponse:
    """Persist one ``crypto_profiles`` row and the matching audit entry.

    ``profile_type`` is computed here. It is not accepted from the client.
    This handler does not evaluate the policy gate; it requires a prior
    ``policy_decisions`` row for the same document (FR-6). A ``deny`` still
    counts. It does not encrypt the document and does not change
    ``documents.current_status``.

    SECURITY CAVEAT: liboqs is NOT independently audited, and OQS-OpenSSL is
    documented by its own maintainers as development and interop-testing only,
    not production-supported. Do not claim audited-grade or FIPS-certified
    guarantees that the library does not back up.

    Raises:
        HTTPException: 404 if the trust score is unknown, 422 if no policy
            decision exists for the document or the stored score cannot be
            mapped.
    """
    trust_row = trust_repo.get_trust_score(session, request.trust_score_id)
    if trust_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_unknown_trust_score_detail(request.trust_score_id),
        )

    if not policy_repo.document_has_policy_decision(session, trust_row.document_id):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "No policy decision recorded for this document. Evaluate the "
                "gate first via POST /api/v1/policy-decisions."
            ),
        )

    consensus_value = Decimal(str(trust_row.consensus_value))
    try:
        profile_type = select_crypto_profile(float(consensus_value))
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    actor = resolve_seeded_actor(session, caller)
    row = crypto_repo.append_profile(
        session,
        document_id=trust_row.document_id,
        trust_score_id=trust_row.id,
        profile_type=profile_type,
    )
    audit_repo.append_entry(
        session,
        event_type=AuditEventType.CRYPTO_PROFILE_SELECTED.value,
        document_id=trust_row.document_id,
        actor_id=actor.id,
        payload=crypto_repo.profile_selected_audit_payload(
            document_id=trust_row.document_id,
            trust_score_id=trust_row.id,
            crypto_profile_id=row.id,
            profile_type=profile_type,
            consensus_value=consensus_value,
            consensus_version=trust_row.consensus_version,
        ),
    )
    return CryptoProfileResponse(
        id=row.id,
        document_id=trust_row.document_id,
        trust_score_id=trust_row.id,
        profile_type=profile_type,
        consensus_value=consensus_value,
        selected_at=row.selected_at,
    )


def _unknown_trust_score_detail(trust_score_id: UUID) -> str:
    """Explain a 404 in terms of the action the caller needs to take."""
    return (
        f"No trust score with id {trust_score_id}. Compute one first via "
        "POST /api/v1/trust-scores."
    )


@router.post(
    "/crypto-shredding",
    response_model=CryptoShredResponse,
    status_code=status.HTTP_200_OK,
    summary="Permanently shred a document's encryption key",
)
def shred_document_key(
    request: CryptoShredRequest,
    session: DbSession,
    caller: ShredDocumentCaller,
) -> CryptoShredResponse:
    """Destroy a document's encryption key irreversibly.

    Implements PRD FR-8. The document's status becomes ARCHIVED. The audit
    trail proving the request was made and honored is preserved. Since this
    build has no object storage, this simulates key destruction by logging the
    event and updating the document status.
    """
    from datetime import datetime, timezone

    document = documents_repo.get_document(
        session, request.document_id, for_update=True
    )
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{request.document_id}' was not found.",
        )

    actor = resolve_seeded_actor(session, caller)
    if actor.id != document.uploaded_by:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Only the data owner who uploaded the document can shred it.",
        )

    if document.current_status == DocumentStatus.ARCHIVED:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="Document is already shredded (archived).",
        )

    previous_status = document.current_status.value
    documents_repo.mark_archived(session, document)

    audit_repo.append_entry(
        session,
        event_type=AuditEventType.DOCUMENT_SHREDDED.value,
        document_id=document.id,
        actor_id=actor.id,
        payload={
            "document_id": str(document.id),
            "action": "crypto_key_shredded",
            "previous_status": previous_status,
            "status": "archived",
        },
    )

    return CryptoShredResponse(
        document_id=document.id,
        shredded_at=datetime.now(timezone.utc),
        status="shredded",
    )
