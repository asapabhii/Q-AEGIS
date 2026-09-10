"""Audit log read and verification, ``SPEC.md`` 3.8, ``PRD.md`` FR-7, FR-15.

``GET /audit/entries`` is the viewer: one document's chain, genesis first.
``GET /audit/verify`` is the independent check. The list does not carry a
validity flag; an auditor who trusts ``is_valid`` on the same response that
served the rows is not verifying independently.

Roles whose personas in ``PRD.md`` Section 5 need the trail:

- ``AUDITOR``: FR-15 requires viewing the chain and triggering verification.
- ``SECURITY_ADMIN``: monitors risk and protection status across the system.
- ``SECURITY_ANALYST``: reviews classifications and overrides.

``COMPLIANCE_OFFICER``, ``DATA_OWNER``, ``CISO``, and ``ENGINEER`` are
excluded: a data owner's stated need is a summary of their own document
(FR-16), and CISO/engineer are not given a verify or viewer action in
Section 5.

Role check is enforced server-side through :mod:`app.api.deps`. A missing or
unrecognized header returns 401 or 403 before any database access occurs.
"""

from datetime import datetime
from typing import Annotated, Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.api.deps import DbSession, require_role
from app.audit.service import RangeVerificationResult, verify_chain_range
from app.db.enums import UserRole
from app.db.repositories import documents as documents_repo
from app.db.repositories.audit import AuditChainError, load_chain

router = APIRouter(prefix="/audit", tags=["audit"])

#: Roles permitted to verify the audit log chain (``PRD.md`` FR-7, FR-15).
VerifyChainCaller = Annotated[
    UserRole,
    Depends(
        require_role(
            UserRole.AUDITOR,
            UserRole.SECURITY_ADMIN,
            UserRole.SECURITY_ANALYST,
        )
    ),
]


class VerifyRangeResponse(BaseModel):
    """Response from the chain-prefix verification endpoint.

    Both roots are returned so a caller can compare them independently. A bare
    ``is_valid: false`` gives an auditor nothing to act on.

    Verification is always a prefix from genesis through ``end_index``. A
    stored Merkle root on entry N covers ``0..N``, so an arbitrary start
    offset cannot be checked against it.
    """

    is_valid: bool
    computed_root: str
    stored_root: str
    end_index: int
    entry_count: int
    document_id: UUID | None


class AuditEntryResponse(BaseModel):
    """One chain row. ``frontier`` is omitted; it is write-path state."""

    id: UUID
    index: int
    actor_id: UUID | None
    event_type: str
    payload: dict[str, Any]
    payload_hash: str
    prev_hash: str | None
    merkle_root_at_time: str
    created_at: datetime


class AuditChainResponse(BaseModel):
    """One document's chain in link order, genesis first. Not a verdict."""

    document_id: UUID
    count: int
    entries: list[AuditEntryResponse]


@router.get(
    "/entries",
    response_model=AuditChainResponse,
    summary="List one document's audit chain",
)
def list_audit_entries(
    session: DbSession,
    _caller: VerifyChainCaller,
    document_id: Annotated[
        UUID,
        Query(description="Document whose chain to return. Required."),
    ],
) -> AuditChainResponse:
    """Return the full chain for ``document_id``, genesis first.

    Order follows ``prev_hash`` links, not ``created_at``. Entries written
    in one transaction share ``now()`` and a timestamp sort would lie.
    Unknown document is 404. An existing document with no entries is an
    empty list. A broken chain is 409. Writes nothing.

    Raises:
        HTTPException: 404 if the document does not exist, 409 if the
            stored rows are not one chain.
    """
    if documents_repo.get_document(session, document_id) is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document '{document_id}' was not found.",
        )
    try:
        chain = load_chain(session, document_id)
    except AuditChainError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc

    return AuditChainResponse(
        document_id=document_id,
        count=len(chain),
        entries=[
            AuditEntryResponse(
                id=entry.id,
                index=index,
                actor_id=entry.actor_id,
                event_type=entry.event_type,
                payload=entry.payload,
                payload_hash=entry.payload_hash,
                prev_hash=entry.prev_hash,
                merkle_root_at_time=entry.merkle_root_at_time,
                created_at=entry.created_at,
            )
            for index, entry in enumerate(chain)
        ],
    )


@router.get(
    "/verify",
    response_model=VerifyRangeResponse,
    summary="Verify a prefix of the audit log chain",
)
def verify_audit_range(
    session: DbSession,
    _caller: VerifyChainCaller,
    document_id: Annotated[
        UUID | None,
        Query(
            description=(
                "Document whose chain to verify. Omit for the system chain "
                "(events with no document)."
            )
        ),
    ] = None,
    end_index: Annotated[
        int | None,
        Query(
            ge=0,
            description=(
                "Zero-based index of the last entry to verify (inclusive). "
                "The prefix 0..end_index is verified. Defaults to the chain "
                "tail."
            ),
        ),
    ] = None,
) -> VerifyRangeResponse:
    """Verify the prefix of the audit log chain through ``end_index``.

    Recomputes the Merkle root from the stored payloads and compares it
    against the root recorded when the last entry in the prefix was written.
    No stored validity flag is consulted; the computation is fully independent.

    Honest limit: ``prev_hash`` links rows but is not itself covered by
    ``payload_hash``, so an attacker with write access to the database could
    rebuild a consistent chain structure. ``merkle_root_at_time`` plus external
    anchoring of that root is what makes such rewriting detectable. The chain
    alone must not be described as tamper-proof.

    Both roots are returned in the response so a discrepancy is actionable.
    """
    try:
        result: RangeVerificationResult = verify_chain_range(
            session,
            document_id,
            end_index=end_index,
        )
    except AuditChainError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(exc),
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    return VerifyRangeResponse(
        is_valid=result.is_valid,
        computed_root=result.computed_root,
        stored_root=result.stored_root,
        end_index=result.end_index,
        entry_count=result.entry_count,
        document_id=result.document_id,
    )
