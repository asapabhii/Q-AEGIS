"""Audit log service layer, ``SPEC.md`` 3.8, ``PRD.md`` FR-7.

This module provides independent verification of the audit log chain. The
verification implemented here recomputes the Merkle root from stored payloads
and compares it against the value recorded at write time. It does NOT consult
any stored "valid" flag or any value this system set at write time — the root
is recomputed entirely from the payloads themselves.

Three services are offered, all reading the chain in link order and none
trusting a stored verdict. :func:`verify_chain_range` recomputes and compares a
whole prefix. :func:`build_inclusion_proof` produces an RFC 6962 audit path so
an auditor can confirm one entry belongs under a root without the rest of the
log. :func:`build_consistency_proof` produces a proof that a later root is an
append-only extension of an earlier one. The pure verification of the proofs
lives in :mod:`app.audit.merkle`; this module only assembles them from stored
rows.

A stored ``merkle_root_at_time`` on entry N is the root of the prefix
``0..N``, never of an arbitrary window ``start..N``. This service therefore
verifies prefixes only: from the genesis entry through ``end_index``. There is
no ``start_index`` parameter, because accepting one would either ignore it or
compare a sub-window against a prefix root, both of which lie to the caller.

Honest limit (also stated in ``docs/data-dictionary.md``): ``prev_hash`` links
rows but is not itself covered by ``payload_hash``, so an attacker with write
access to the database could recompute a whole consistent chain.
``merkle_root_at_time`` plus external anchoring of that root is what makes
such rewriting detectable. The chain alone must not be described as
tamper-proof; it stops accidental corruption and detects when paired with an
externally anchored root.

``build()`` and ``verify()`` from :mod:`app.audit.merkle` remain pure with no
side effects. Only this module touches the database; the pure functions stay
free of I/O so an auditor can call them with an exported dataset and a root
obtained independently, which is what ``PRD.md`` FR-7 requires.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy.orm import Session

from app.audit.checkpoint import (
    CHECKPOINT_SIGNATURE_ALGORITHM,
    checkpoint_signing_input,
    generate_signing_keypair,
    sign_checkpoint,
    verify_checkpoint_signature,
)
from app.audit.merkle import (
    ConsistencyProof,
    InclusionProof,
    VerificationResult,
    build,
    canonicalize,
    consistency_proof,
    hash_leaf,
    inclusion_proof,
    verify,
)
from app.crypto.key_management import unwrap_dek, wrap_dek
from app.db.repositories import checkpoint as checkpoint_repo
from app.db.repositories.audit import load_chain


@dataclass(frozen=True)
class RangeVerificationResult:
    """Result of verifying a prefix of a document's audit chain.

    Both roots are returned so a failure report can show what the entries
    actually produce against what was stored. A bare boolean gives an auditor
    nothing to act on.

    Attributes:
        is_valid: True only if the recomputed root matches the stored root at
            the end of the prefix.
        computed_root: Root recomputed from the prefix payloads, with no
            reliance on any stored validity claim.
        stored_root: The ``merkle_root_at_time`` stored on the last entry in
            the prefix.
        end_index: Zero-based index of the last entry verified (inclusive).
        entry_count: Number of entries in the verified prefix (always
            ``end_index + 1``).
        document_id: The document chain that was verified, or ``None`` for the
            system chain.
    """

    is_valid: bool
    computed_root: str
    stored_root: str
    end_index: int
    entry_count: int
    document_id: UUID | None


def verify_chain_range(
    session: Session,
    document_id: UUID | None,
    *,
    end_index: int | None = None,
) -> RangeVerificationResult:
    """Verify the prefix of a document's audit chain through ``end_index``.

    Loads the full chain in link order, takes entries ``0..end_index``, then
    calls :func:`app.audit.merkle.verify` against the stored root on that last
    entry. The stored root is read but never trusted as a verdict: the
    recomputed root is what determines ``is_valid``, exactly as FR-7 requires.

    Honest limit: ``prev_hash`` is not covered by ``payload_hash``. A party
    with write access could rebuild the link structure around altered entries.
    External anchoring of ``merkle_root_at_time`` is what makes that detectable,
    not the chain structure alone.

    Args:
        session: Active SQLAlchemy session.
        document_id: Document whose chain to verify, or ``None`` for the system
            chain of events with no document.
        end_index: Zero-based index of the last entry to include (inclusive).
            Defaults to the last entry in the chain.

    Returns:
        A :class:`RangeVerificationResult` containing the verdict and both
        roots so a caller can report discrepancies.

    Raises:
        ValueError: if ``end_index`` is negative or falls outside the chain
            length, or if the chain is empty.
        app.db.repositories.audit.AuditChainError: if the stored chain is
            broken or forked.
    """
    if end_index is not None and end_index < 0:
        raise ValueError(f"end_index must be non-negative, got {end_index}.")

    chain = load_chain(session, document_id)
    chain_length = len(chain)

    if chain_length == 0:
        raise ValueError(
            f"Chain for document_id={document_id!r} has no entries; "
            "there is nothing to verify."
        )

    resolved_end = chain_length - 1 if end_index is None else end_index

    if resolved_end >= chain_length:
        raise ValueError(
            f"end_index ({resolved_end}) is out of range for a chain of "
            f"{chain_length} entries (max index {chain_length - 1})."
        )

    prefix = chain[: resolved_end + 1]
    entry_payloads = [canonicalize(entry.payload) for entry in prefix]
    stored_root = chain[resolved_end].merkle_root_at_time

    result: VerificationResult = verify(entry_payloads, stored_root)

    return RangeVerificationResult(
        is_valid=result.is_valid,
        computed_root=result.computed_root,
        stored_root=stored_root,
        end_index=resolved_end,
        entry_count=len(prefix),
        document_id=document_id,
    )


@dataclass(frozen=True)
class InclusionProofResult:
    """A single-entry inclusion proof plus everything needed to check it offline.

    Handed to an auditor who wants to confirm one entry belongs under a root
    without pulling the whole chain. The auditor recomputes the leaf hash from
    ``payload`` (or trusts ``leaf_hash``) and calls
    :func:`app.audit.merkle.verify_inclusion` against a root obtained
    independently. ``root`` is included as a convenience, recomputed here from
    the tree's payloads, never read back from a stored validity claim.

    Attributes:
        proof: The RFC 6962 audit path and its position/size metadata.
        payload: The canonicalised entry being proved, as stored.
        leaf_hash: ``hash_leaf`` over that entry's canonical bytes — the value
            verification starts from.
        root: Merkle root of the tree the proof is against, recomputed from the
            prefix ``0..tree_size - 1``.
        document_id: The chain proved against, or ``None`` for the system chain.
    """

    proof: InclusionProof
    payload: dict
    leaf_hash: str
    root: str
    document_id: UUID | None


@dataclass(frozen=True)
class ConsistencyProofResult:
    """A consistency proof plus the two roots it relates, for offline checking.

    Lets an auditor confirm the chain grew by appending only — that the entries
    an earlier root committed to are unchanged under a later one. Both roots are
    recomputed here from stored payloads, not read from stored claims, so an
    auditor can re-derive them independently and call
    :func:`app.audit.merkle.verify_consistency`.

    Attributes:
        proof: The RFC 6962 consistency nodes and the two sizes.
        old_root: Root of the prefix ``0..old_size - 1``.
        new_root: Root of the prefix ``0..new_size - 1``.
        document_id: The chain proved against, or ``None`` for the system chain.
    """

    proof: ConsistencyProof
    old_root: str
    new_root: str
    document_id: UUID | None


def build_inclusion_proof(
    session: Session,
    document_id: UUID | None,
    leaf_index: int,
    *,
    tree_size: int | None = None,
) -> InclusionProofResult:
    """Produce an inclusion proof for one entry in a document's chain.

    Loads the chain in link order, takes the prefix ``0..tree_size - 1`` (the
    whole chain by default), and builds an RFC 6962 audit path for the entry at
    ``leaf_index``. The returned root is recomputed from the prefix payloads, so
    a verifier never has to trust a value this system stored.

    Args:
        session: Active SQLAlchemy session.
        document_id: Document whose chain to prove against, or ``None`` for the
            system chain.
        leaf_index: Zero-based position of the entry to prove.
        tree_size: Size of the tree to prove membership in. Defaults to the full
            chain length. Lets a caller prove membership under an older,
            already-anchored root rather than only the current one.

    Returns:
        An :class:`InclusionProofResult`.

    Raises:
        ValueError: if the chain is empty, ``tree_size`` is out of range, or
            ``leaf_index`` is not within ``0..tree_size - 1``.
        app.db.repositories.audit.AuditChainError: if the stored chain is
            broken or forked.
    """
    chain = load_chain(session, document_id)
    chain_length = len(chain)
    if chain_length == 0:
        raise ValueError(
            f"Chain for document_id={document_id!r} has no entries; "
            "there is nothing to prove."
        )

    resolved_size = chain_length if tree_size is None else tree_size
    if not 1 <= resolved_size <= chain_length:
        raise ValueError(
            f"tree_size ({resolved_size}) must be between 1 and the chain "
            f"length ({chain_length})."
        )
    if not 0 <= leaf_index < resolved_size:
        raise ValueError(
            f"leaf_index ({leaf_index}) is out of range for a tree of "
            f"{resolved_size} entries (max index {resolved_size - 1})."
        )

    prefix = chain[:resolved_size]
    payloads = [canonicalize(entry.payload) for entry in prefix]
    proof = inclusion_proof(payloads, leaf_index)

    return InclusionProofResult(
        proof=proof,
        payload=chain[leaf_index].payload,
        leaf_hash=hash_leaf(payloads[leaf_index]),
        root=build(payloads).root,
        document_id=document_id,
    )


def build_consistency_proof(
    session: Session,
    document_id: UUID | None,
    old_size: int,
    *,
    new_size: int | None = None,
) -> ConsistencyProofResult:
    """Produce a consistency proof between two prefixes of a document's chain.

    Proves the prefix of ``new_size`` entries contains the prefix of
    ``old_size`` as an unaltered, in-order head — the append-only guarantee that
    makes an anchored root worth anchoring. Both roots are recomputed from
    stored payloads here so an auditor can re-derive them independently.

    Args:
        session: Active SQLAlchemy session.
        document_id: Document whose chain to prove over, or ``None`` for the
            system chain.
        old_size: Entry count of the earlier prefix.
        new_size: Entry count of the later prefix. Defaults to the full chain.

    Returns:
        A :class:`ConsistencyProofResult`.

    Raises:
        ValueError: if the chain is empty, or the sizes are out of range or not
            ordered ``0 <= old_size <= new_size <= chain length``.
        app.db.repositories.audit.AuditChainError: if the stored chain is
            broken or forked.
    """
    chain = load_chain(session, document_id)
    chain_length = len(chain)
    if chain_length == 0:
        raise ValueError(
            f"Chain for document_id={document_id!r} has no entries; "
            "there is nothing to prove."
        )

    resolved_new = chain_length if new_size is None else new_size
    if not 1 <= resolved_new <= chain_length:
        raise ValueError(
            f"new_size ({resolved_new}) must be between 1 and the chain "
            f"length ({chain_length})."
        )
    if not 0 <= old_size <= resolved_new:
        raise ValueError(
            f"old_size ({old_size}) must be between 0 and new_size "
            f"({resolved_new})."
        )

    payloads = [canonicalize(entry.payload) for entry in chain[:resolved_new]]
    proof = consistency_proof(payloads, old_size)

    return ConsistencyProofResult(
        proof=proof,
        old_root=build(payloads[:old_size]).root,
        new_root=build(payloads).root,
        document_id=document_id,
    )


@dataclass(frozen=True)
class SignedCheckpointResult:
    """A freshly issued Signed Tree Head plus what a verifier needs to check it.

    Returned from :func:`create_checkpoint`. ``public_key`` is the hex key the
    signature verifies under; an auditor pins it out-of-band and re-runs
    :func:`app.audit.checkpoint.verify_checkpoint_signature`.

    Attributes:
        checkpoint_id: Primary key of the persisted checkpoint row.
        document_id: Chain committed to, or ``None`` for the system chain.
        tree_size: Number of leaves the root covers.
        merkle_root: Hex Merkle root over the prefix ``0..tree_size-1``.
        signed_at: Issue time folded into the signed bytes.
        algorithm: Signature mechanism, e.g. ``"ML-DSA-87"``.
        signature: Hex-encoded detached signature.
        signing_key_id: The key that produced the signature.
        public_key: Hex public key the signature verifies under.
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


@dataclass(frozen=True)
class CheckpointVerificationResult:
    """The outcome of independently re-checking a stored checkpoint.

    Two orthogonal facts, both required for a checkpoint to still hold:

    - ``signature_valid``: the ML-DSA-87 signature over the checkpoint's own
      fields verifies under the key that signed it. This is what an operator
      cannot forge after the fact.
    - ``root_matches``: the root recomputed now from the stored payloads equals
      the root the checkpoint committed to. A valid signature with a mismatched
      root is the tampering signal: the chain was rewritten after anchoring.

    ``is_valid`` is the conjunction. Both roots are returned so a discrepancy is
    actionable rather than a bare boolean.

    Attributes:
        is_valid: ``signature_valid and root_matches``.
        signature_valid: Whether the signature verifies under the stored key.
        root_matches: Whether the recomputed root equals the committed root.
        stored_root: The root the checkpoint committed to.
        recomputed_root: The root recomputed now from the chain's payloads, or
            an empty string when the chain is now shorter than ``tree_size``.
        tree_size: The prefix size the checkpoint covers.
        signed_at: The checkpoint's issue time.
        algorithm: Signature mechanism recorded on the signing key.
        public_key: Hex public key the signature was checked against.
        document_id: Chain the checkpoint commits to, or ``None``.
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


@dataclass(frozen=True)
class ActiveSigningKeyInfo:
    """The active checkpoint signing key's public half, for pinning.

    Attributes:
        signing_key_id: Primary key of the active signing-key row.
        algorithm: Signature mechanism, e.g. ``"ML-DSA-87"``.
        public_key: Hex-encoded raw public key.
        created_at: When the key was created.
    """

    signing_key_id: UUID
    algorithm: str
    public_key: str
    created_at: datetime


def _load_or_create_signing_secret(
    session: Session, *, master_key: bytes | None
) -> tuple[UUID, bytes]:
    """Return ``(signing_key_id, secret_key_bytes)`` for the active signing key.

    Uses the current active key when one exists, unwrapping its secret under the
    master key. Otherwise generates a fresh ML-DSA-87 keypair, wraps the secret
    under the master key, and persists it — so the first checkpoint bootstraps
    the log's key and every later one reuses it, which is what makes a series of
    checkpoints attributable to one pinned public key.
    """
    active = checkpoint_repo.get_active_signing_key(session)
    if active is not None:
        secret_key = unwrap_dek(active.wrapped_secret_key, master_key=master_key)
        return active.id, secret_key

    public_key, secret_key = generate_signing_keypair()
    wrapped = wrap_dek(secret_key, master_key=master_key)
    row = checkpoint_repo.insert_signing_key(
        session,
        algorithm=CHECKPOINT_SIGNATURE_ALGORITHM,
        public_key=public_key.hex(),
        wrapped_secret_key=wrapped,
    )
    return row.id, secret_key


def create_checkpoint(
    session: Session,
    document_id: UUID | None,
    *,
    tree_size: int | None = None,
    master_key: bytes | None = None,
) -> SignedCheckpointResult:
    """Issue a Signed Tree Head over a chain's prefix and persist it.

    Recomputes the Merkle root over the prefix ``0..tree_size-1`` from the stored
    payloads, signs the canonical commitment with ML-DSA-87, and stores it. The
    signed bytes bind ``document_id``, ``tree_size``, ``signed_at``, and the
    root, so none can be altered afterwards without invalidating the signature.

    Does not commit: the checkpoint is written in the caller's transaction.

    Args:
        session: Active session, inside a transaction.
        document_id: Chain to anchor, or ``None`` for the system chain.
        tree_size: Prefix size to commit to. Defaults to the full chain length.
        master_key: Optional master-key override for tests; defaults to
            ``CRYPTO_MASTER_KEY``.

    Returns:
        A :class:`SignedCheckpointResult`.

    Raises:
        ValueError: if the chain is empty or ``tree_size`` is out of range.
        app.db.repositories.audit.AuditChainError: if the stored chain is broken
            or forked.
        app.crypto.exceptions.LiboqsUnavailableError: if ML-DSA-87 is
            unavailable, so a checkpoint is never silently left unsigned.
        app.crypto.exceptions.CryptoConfigurationError: if no master key is
            configured to wrap or unwrap the signing secret.
    """
    chain = load_chain(session, document_id)
    chain_length = len(chain)
    if chain_length == 0:
        raise ValueError(
            f"Chain for document_id={document_id!r} has no entries; "
            "there is nothing to checkpoint."
        )

    resolved_size = chain_length if tree_size is None else tree_size
    if not 1 <= resolved_size <= chain_length:
        raise ValueError(
            f"tree_size ({resolved_size}) must be between 1 and the chain "
            f"length ({chain_length})."
        )

    payloads = [canonicalize(entry.payload) for entry in chain[:resolved_size]]
    merkle_root = build(payloads).root
    signed_at = datetime.now(timezone.utc)

    signing_key_id, secret_key = _load_or_create_signing_secret(
        session, master_key=master_key
    )
    signing_input = checkpoint_signing_input(
        document_id=document_id,
        tree_size=resolved_size,
        signed_at=signed_at,
        merkle_root=merkle_root,
    )
    signature = sign_checkpoint(signing_input, secret_key)
    active_key = checkpoint_repo.get_signing_key(session, signing_key_id)

    checkpoint = checkpoint_repo.insert_checkpoint(
        session,
        document_id=document_id,
        signing_key_id=signing_key_id,
        tree_size=resolved_size,
        merkle_root=merkle_root,
        signature=signature.hex(),
        signed_at=signed_at,
    )

    return SignedCheckpointResult(
        checkpoint_id=checkpoint.id,
        document_id=document_id,
        tree_size=resolved_size,
        merkle_root=merkle_root,
        signed_at=signed_at,
        algorithm=CHECKPOINT_SIGNATURE_ALGORITHM,
        signature=signature.hex(),
        signing_key_id=signing_key_id,
        public_key=active_key.public_key if active_key is not None else "",
    )


def verify_checkpoint(
    session: Session, checkpoint_id: UUID
) -> CheckpointVerificationResult:
    """Re-check a stored checkpoint against the chain as it stands now.

    Rebuilds the signed bytes from the checkpoint's own fields and verifies the
    ML-DSA-87 signature under the key that signed it, then recomputes the Merkle
    root from the stored payloads and compares it to the committed root. A valid
    signature with a mismatched root is the append-only guarantee firing: the
    chain was rewritten after it was anchored.

    Args:
        session: Active session.
        checkpoint_id: The checkpoint to verify.

    Returns:
        A :class:`CheckpointVerificationResult` carrying both facts and both
        roots.

    Raises:
        ValueError: if no checkpoint or signing key with those ids exists.
        app.db.repositories.audit.AuditChainError: if the stored chain is broken
            or forked.
        app.crypto.exceptions.LiboqsUnavailableError: if ML-DSA-87 is
            unavailable to verify the signature.
    """
    checkpoint = checkpoint_repo.get_checkpoint(session, checkpoint_id)
    if checkpoint is None:
        raise ValueError(f"Checkpoint '{checkpoint_id}' was not found.")

    signing_key = checkpoint_repo.get_signing_key(session, checkpoint.signing_key_id)
    if signing_key is None:
        raise ValueError(
            f"Signing key '{checkpoint.signing_key_id}' for checkpoint "
            f"'{checkpoint_id}' was not found."
        )

    signing_input = checkpoint_signing_input(
        document_id=checkpoint.document_id,
        tree_size=checkpoint.tree_size,
        signed_at=checkpoint.signed_at,
        merkle_root=checkpoint.merkle_root,
    )
    signature_valid = verify_checkpoint_signature(
        signing_input,
        bytes.fromhex(checkpoint.signature),
        bytes.fromhex(signing_key.public_key),
    )

    chain = load_chain(session, checkpoint.document_id)
    if checkpoint.tree_size <= len(chain):
        payloads = [
            canonicalize(entry.payload) for entry in chain[: checkpoint.tree_size]
        ]
        recomputed_root = build(payloads).root
    else:
        # The chain is now shorter than the prefix this checkpoint committed to,
        # which is itself a rewriting signal: there is no matching prefix to hash.
        recomputed_root = ""
    root_matches = recomputed_root == checkpoint.merkle_root

    return CheckpointVerificationResult(
        is_valid=signature_valid and root_matches,
        signature_valid=signature_valid,
        root_matches=root_matches,
        stored_root=checkpoint.merkle_root,
        recomputed_root=recomputed_root,
        tree_size=checkpoint.tree_size,
        signed_at=checkpoint.signed_at,
        algorithm=signing_key.algorithm,
        public_key=signing_key.public_key,
        document_id=checkpoint.document_id,
    )


def get_active_signing_key_info(session: Session) -> ActiveSigningKeyInfo | None:
    """Return the active signing key's public half, or ``None`` if none exists.

    This is what an auditor pins: the public key every current checkpoint
    verifies under. It is created lazily by the first :func:`create_checkpoint`,
    so ``None`` here means no checkpoint has ever been issued.
    """
    active = checkpoint_repo.get_active_signing_key(session)
    if active is None:
        return None
    return ActiveSigningKeyInfo(
        signing_key_id=active.id,
        algorithm=active.algorithm,
        public_key=active.public_key,
        created_at=active.created_at,
    )
