"""Audit log verification endpoint, ``SPEC.md`` 3.8, ``PRD.md`` FR-7.

Exposes a prefix-verification endpoint for the tamper-evident audit log.
The endpoint is restricted to roles whose personas in ``PRD.md`` Section 5
include a need to independently verify the audit trail:

- ``AUDITOR``: FR-15 requires an auditor to independently verify the full
  chain. This is that auditor's primary endpoint.
- ``SECURITY_ADMIN``: monitors risk and protection status across the system,
  which requires being able to verify the integrity of the record.
- ``SECURITY_ANALYST``: reviews classifications and overrides, which requires
  being able to verify the log entries around a decision.

``COMPLIANCE_OFFICER``, ``DATA_OWNER``, ``CISO``, and ``ENGINEER`` are
deliberately excluded: chain verification belongs to the auditor persona,
a data owner's stated need is a summary of their own document (FR-16), and
CISO/engineer are not given a verify action in Section 5.

Role check is enforced server-side through :mod:`app.api.deps`. A missing or
unrecognized header returns 401 or 403 before any database access occurs.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.api.deps import DbSession, require_role
from app.audit.service import RangeVerificationResult, verify_chain_range
from app.db.enums import UserRole
from app.db.repositories.audit import AuditChainError

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
