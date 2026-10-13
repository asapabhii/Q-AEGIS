"""Audit log read and verification, ``SPEC.md`` 3.8, ``PRD.md`` FR-7, FR-15.

``GET /audit/entries`` is the viewer: one document's chain, genesis first.
``GET /audit/verify`` is the independent whole-prefix check. The list does not
carry a validity flag; an auditor who trusts ``is_valid`` on the same response
that served the rows is not verifying independently.

``GET /audit/inclusion-proof`` and ``GET /audit/consistency-proof`` return RFC
6962 proofs an auditor re-checks offline with :mod:`app.audit.merkle`: the first
proves one entry sits under a root without the rest of the log, the second
proves a later root only appended to an earlier one. Both return the roots
recomputed from stored payloads, so the client verifies against a root it
trusts rather than one asserted here.

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

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from pydantic import BaseModel

from app.api.deps import DbSession, require_role
from app.audit.service import (
    ActiveSigningKeyInfo,
    CheckpointVerificationResult,
    ConsistencyProofResult,
    InclusionProofResult,
    RangeVerificationResult,
    SignedCheckpointResult,
    build_consistency_proof,
    build_inclusion_proof,
    create_checkpoint,
    get_active_signing_key_info,
    verify_chain_range,
    verify_checkpoint,
)
from app.crypto.exceptions import CryptoConfigurationError, LiboqsUnavailableError
from app.db.enums import UserRole
from app.db.repositories import checkpoint as checkpoint_repo
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

#: Roles permitted to *issue* a Signed Tree Head (``PRD.md`` FR-7). Stricter
#: than reading or verifying: issuing a checkpoint mints tamper-evidence and,
#: on first use, bootstraps the append-only signing key. An analyst reviews the
#: trail but does not anchor it; that is an auditor's or security admin's act.
CheckpointCreator = Annotated[
    UserRole,
    Depends(
        require_role(
            UserRole.AUDITOR,
            UserRole.SECURITY_ADMIN,
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


class InclusionProofResponse(BaseModel):
    """An RFC 6962 inclusion proof for one entry, checkable offline.

    Everything needed to run ``verify_inclusion`` without re-reading the log:
    the sibling ``audit_path`` from leaf to root, the ``leaf_index`` and
    ``tree_size`` that fix each step's orientation, the ``leaf_hash`` to start
    from, and the ``root`` recomputed from the tree's payloads. An auditor
    trusts a root obtained independently, not the one echoed here.
    """

    document_id: UUID | None
    leaf_index: int
    tree_size: int
    audit_path: list[str]
    leaf_hash: str
    root: str
    payload: dict[str, Any]


class ConsistencyProofResponse(BaseModel):
    """An RFC 6962 consistency proof between two chain prefixes.

    Proves the ``new_size`` prefix contains the ``old_size`` prefix as an
    unaltered head. Carries both roots, recomputed from stored payloads, so a
    caller can re-derive them and run ``verify_consistency`` independently.
    """

    document_id: UUID | None
    old_size: int
    new_size: int
    nodes: list[str]
    old_root: str
    new_root: str


class CreateCheckpointRequest(BaseModel):
    """Body for issuing a Signed Tree Head.

    ``document_id`` omitted (or null) anchors the system chain. ``tree_size``
    omitted anchors the full chain as it stands; supplying a smaller prefix
    lets an auditor re-anchor an already-published size.
    """

    document_id: UUID | None = None
    tree_size: int | None = None


class SignedCheckpointResponse(BaseModel):
    """A freshly issued Signed Tree Head and what a verifier needs to check it.

    ``public_key`` is the hex ML-DSA-87 key the ``signature`` verifies under. An
    auditor pins it out-of-band; every later verification runs against the key
    named by ``signing_key_id``, not against a key this system asserts at read
    time.

    SECURITY CAVEAT: the signature is produced with liboqs, which is NOT
    independently audited; treat the anchoring as tamper-evidence, not a
    certified guarantee.
    """

    checkpoint_id: UUID
    document_id: UUID | None
    tree_size: int
    merkle_root: str
    signed_at: datetime
    algorithm: str
    signature: str
    signing_key_id: UUID
    public_key: str


class CheckpointVerificationResponse(BaseModel):
    """The outcome of independently re-checking a stored checkpoint.

    ``signature_valid`` is whether the ML-DSA-87 signature verifies under the
    key that signed it; ``root_matches`` is whether the root recomputed now from
    the stored payloads equals the committed root. ``is_valid`` is their
    conjunction. A valid signature with a mismatched root is the tampering
    signal: the chain was rewritten after it was anchored. Both roots are
    returned so a discrepancy is actionable.
    """

    is_valid: bool
    signature_valid: bool
    root_matches: bool
    stored_root: str
    recomputed_root: str
    tree_size: int
    signed_at: datetime
    algorithm: str
    public_key: str
    document_id: UUID | None


class SigningKeyResponse(BaseModel):
    """The active checkpoint signing key's public half, for pinning.

    The public key is not a secret; it is published precisely so an auditor can
    pin it and verify checkpoints offline. The secret half never leaves the
    server and is wrapped under the master key at rest.
    """

    signing_key_id: UUID
    algorithm: str
    public_key: str
    created_at: datetime


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


@router.get(
    "/inclusion-proof",
    response_model=InclusionProofResponse,
    summary="Prove one entry's inclusion under a Merkle root",
)
def get_inclusion_proof(
    session: DbSession,
    _caller: VerifyChainCaller,
    leaf_index: Annotated[
        int,
        Query(ge=0, description="Zero-based position of the entry to prove."),
    ],
    document_id: Annotated[
        UUID | None,
        Query(
            description=(
                "Document whose chain to prove against. Omit for the system "
                "chain (events with no document)."
            )
        ),
    ] = None,
    tree_size: Annotated[
        int | None,
        Query(
            ge=1,
            description=(
                "Size of the tree to prove membership in. Defaults to the full "
                "chain. Use an older size to prove against an already-anchored "
                "root."
            ),
        ),
    ] = None,
) -> InclusionProofResponse:
    """Return an RFC 6962 inclusion proof for a single audit entry.

    The proof is O(log n) sibling hashes; a verifier confirms the entry sits at
    ``leaf_index`` under ``root`` without being handed the rest of the chain.
    The root is recomputed from stored payloads, never read from a stored
    validity claim.

    Raises:
        HTTPException: 409 if the stored chain is broken or forked, 422 if the
            index or tree size is out of range or the chain is empty.
    """
    try:
        result: InclusionProofResult = build_inclusion_proof(
            session, document_id, leaf_index, tree_size=tree_size
        )
    except AuditChainError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    return InclusionProofResponse(
        document_id=result.document_id,
        leaf_index=result.proof.leaf_index,
        tree_size=result.proof.tree_size,
        audit_path=list(result.proof.audit_path),
        leaf_hash=result.leaf_hash,
        root=result.root,
        payload=result.payload,
    )


@router.get(
    "/consistency-proof",
    response_model=ConsistencyProofResponse,
    summary="Prove the chain grew by appending only",
)
def get_consistency_proof(
    session: DbSession,
    _caller: VerifyChainCaller,
    old_size: Annotated[
        int,
        Query(ge=0, description="Entry count of the earlier prefix."),
    ],
    document_id: Annotated[
        UUID | None,
        Query(
            description=(
                "Document whose chain to prove over. Omit for the system chain "
                "(events with no document)."
            )
        ),
    ] = None,
    new_size: Annotated[
        int | None,
        Query(
            ge=1,
            description=(
                "Entry count of the later prefix. Defaults to the full chain."
            ),
        ),
    ] = None,
) -> ConsistencyProofResponse:
    """Return an RFC 6962 consistency proof between two chain prefixes.

    Proves the later prefix contains the earlier one unchanged and in order —
    the append-only property that makes external anchoring of a root meaningful.
    Both roots are recomputed from stored payloads so a caller can re-derive
    them independently.

    Raises:
        HTTPException: 409 if the stored chain is broken or forked, 422 if the
            sizes are out of range or unordered, or the chain is empty.
    """
    try:
        result: ConsistencyProofResult = build_consistency_proof(
            session, document_id, old_size, new_size=new_size
        )
    except AuditChainError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc

    return ConsistencyProofResponse(
        document_id=result.document_id,
        old_size=result.proof.old_size,
        new_size=result.proof.new_size,
        nodes=list(result.proof.nodes),
        old_root=result.old_root,
        new_root=result.new_root,
    )


@router.post(
    "/checkpoint",
    response_model=SignedCheckpointResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Issue a PQ-signed Signed Tree Head over a chain prefix",
)
def issue_checkpoint(
    session: DbSession,
    _caller: CheckpointCreator,
    request: Annotated[CreateCheckpointRequest, Body()] = CreateCheckpointRequest(),
) -> SignedCheckpointResponse:
    """Anchor a chain's Merkle root now by signing it with ML-DSA-87.

    Recomputes the root over the prefix from stored payloads, signs the
    canonical commitment (which binds ``document_id``, ``tree_size``,
    ``signed_at``, and the root), and persists the Signed Tree Head. The first
    checkpoint bootstraps the append-only signing key; later ones reuse it, so a
    single pinned public key covers the whole series.

    SECURITY CAVEAT: the signature is produced with liboqs, which is NOT
    independently audited. This is tamper-evidence, not a certified guarantee.

    Fails closed: if ML-DSA-87 is unavailable the checkpoint is refused (503)
    rather than left unsigned.

    Raises:
        HTTPException: 409 if the stored chain is broken or forked, 422 if the
            chain is empty or ``tree_size`` is out of range, 503 if liboqs or
            the master key is unavailable.
    """
    try:
        result: SignedCheckpointResult = create_checkpoint(
            session,
            request.document_id,
            tree_size=request.tree_size,
        )
    except AuditChainError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail=str(exc)
        ) from exc
    except (LiboqsUnavailableError, CryptoConfigurationError) as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    return SignedCheckpointResponse(
        checkpoint_id=result.checkpoint_id,
        document_id=result.document_id,
        tree_size=result.tree_size,
        merkle_root=result.merkle_root,
        signed_at=result.signed_at,
        algorithm=result.algorithm,
        signature=result.signature,
        signing_key_id=result.signing_key_id,
        public_key=result.public_key,
    )


@router.get(
    "/checkpoint/{checkpoint_id}/verify",
    response_model=CheckpointVerificationResponse,
    summary="Independently re-verify a stored checkpoint",
)
def verify_stored_checkpoint(
    session: DbSession,
    _caller: VerifyChainCaller,
    checkpoint_id: UUID,
) -> CheckpointVerificationResponse:
    """Re-check a stored Signed Tree Head against the chain as it stands now.

    Verifies the ML-DSA-87 signature under the key that signed it, then
    recomputes the Merkle root from the stored payloads and compares it to the
    committed root. A valid signature over a root that no longer matches is the
    append-only guarantee firing: the chain was rewritten after anchoring.

    Raises:
        HTTPException: 404 if no checkpoint with that id exists, 409 if the
            stored chain is broken or forked, 503 if liboqs is unavailable to
            check the signature.
    """
    try:
        result: CheckpointVerificationResult = verify_checkpoint(session, checkpoint_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
    except AuditChainError as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail=str(exc)
        ) from exc
    except LiboqsUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)
        ) from exc

    return CheckpointVerificationResponse(
        is_valid=result.is_valid,
        signature_valid=result.signature_valid,
        root_matches=result.root_matches,
        stored_root=result.stored_root,
        recomputed_root=result.recomputed_root,
        tree_size=result.tree_size,
        signed_at=result.signed_at,
        algorithm=result.algorithm,
        public_key=result.public_key,
        document_id=result.document_id,
    )


@router.get(
    "/signing-key",
    response_model=SigningKeyResponse,
    summary="Return the active checkpoint signing key for pinning",
)
def get_signing_key(
    session: DbSession,
    _caller: VerifyChainCaller,
) -> SigningKeyResponse:
    """Return the active signing key's public half so an auditor can pin it.

    The key is created lazily by the first issued checkpoint, so a 404 here
    means no checkpoint has ever been anchored. The public key is safe to
    publish; the secret half never leaves the server.

    Raises:
        HTTPException: 404 if no signing key exists yet.
    """
    info: ActiveSigningKeyInfo | None = get_active_signing_key_info(session)
    if info is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=(
                "No signing key exists yet; issue a checkpoint first "
                "(POST /audit/checkpoint)."
            ),
        )
    return SigningKeyResponse(
        signing_key_id=info.signing_key_id,
        algorithm=info.algorithm,
        public_key=info.public_key,
        created_at=info.created_at,
    )


@router.get(
    "/checkpoints",
    response_model=list[SignedCheckpointResponse],
    summary="List a chain's issued checkpoints, oldest prefix first",
)
def list_audit_checkpoints(
    session: DbSession,
    _caller: VerifyChainCaller,
    document_id: Annotated[
        UUID | None,
        Query(
            description=(
                "Chain whose checkpoints to list. Omit for the system chain "
                "(events with no document)."
            )
        ),
    ] = None,
) -> list[SignedCheckpointResponse]:
    """List every Signed Tree Head issued for one chain, oldest prefix first.

    Each row echoes the signature and the public key it verifies under, so a
    caller can re-run verification offline against a pinned key rather than
    trusting a verdict asserted here. Writes nothing.
    """
    checkpoints = checkpoint_repo.list_checkpoints(session, document_id)
    responses: list[SignedCheckpointResponse] = []
    for checkpoint in checkpoints:
        signing_key = checkpoint_repo.get_signing_key(
            session, checkpoint.signing_key_id
        )
        responses.append(
            SignedCheckpointResponse(
                checkpoint_id=checkpoint.id,
                document_id=checkpoint.document_id,
                tree_size=checkpoint.tree_size,
                merkle_root=checkpoint.merkle_root,
                signed_at=checkpoint.signed_at,
                algorithm=(signing_key.algorithm if signing_key is not None else ""),
                signature=checkpoint.signature,
                signing_key_id=checkpoint.signing_key_id,
                public_key=(signing_key.public_key if signing_key is not None else ""),
            )
        )
    return responses
