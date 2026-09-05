"""Audit log service layer, ``SPEC.md`` 3.8, ``PRD.md`` FR-7.

This module provides independent verification of the audit log chain. The
verification implemented here recomputes the Merkle root from stored payloads
and compares it against the value recorded at write time. It does NOT consult
any stored "valid" flag or any value this system set at write time — the root
is recomputed entirely from the payloads themselves.

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
from uuid import UUID

from sqlalchemy.orm import Session

from app.audit.merkle import VerificationResult, canonicalize, verify
from app.db.repositories.audit import load_chain


@dataclass(frozen=True)
class RangeVerificationResult:
    """Result of verifying a contiguous slice of a document's audit chain.

    Both roots are returned so a failure report can show what the entries
    actually produce against what was stored. A bare boolean gives an auditor
    nothing to act on.

    Attributes:
        is_valid: True only if the recomputed root matches the stored root at
            the end of the range.
        computed_root: Root recomputed from the range's payloads, with no
            reliance on any stored validity claim.
        stored_root: The ``merkle_root_at_time`` stored on the last entry in
            the range.
        start_index: Zero-based index of the first entry verified (inclusive).
        end_index: Zero-based index of the last entry verified (inclusive).
        entry_count: Number of entries in the verified range.
        document_id: The document chain that was verified, or ``None`` for the
            system chain.
    """

    is_valid: bool
    computed_root: str
    stored_root: str
    start_index: int
    end_index: int
    entry_count: int
    document_id: UUID | None


def verify_chain_range(
    session: Session,
    document_id: UUID | None,
    *,
    start_index: int = 0,
    end_index: int | None = None,
) -> RangeVerificationResult:
    """Verify a contiguous range of a document's audit chain.

    Loads the full chain in link order, slices the requested range, then calls
    :func:`app.audit.merkle.verify` against the stored root at the end of the
    range. The stored root is read but never trusted as a verdict: the
    recomputed root is what determines ``is_valid``, exactly as FR-7 requires.

    A range that does not start at the chain's beginning is still verifiable.
    The Merkle root stored on the last entry in the slice was computed over the
    whole chain up to that point, so slicing mid-chain is meaningful: you are
    verifying that the first ``end_index + 1`` entries of the chain produce the
    root that was recorded after entry ``end_index`` was appended.

    Honest limit: ``prev_hash`` is not covered by ``payload_hash``. A party
    with write access could rebuild the link structure around altered entries.
    External anchoring of ``merkle_root_at_time`` is what makes that detectable,
    not the chain structure alone.

    Args:
        session: Active SQLAlchemy session.
        document_id: Document whose chain to verify, or ``None`` for the system
            chain of events with no document.
        start_index: Zero-based index of the first entry to include (inclusive,
            defaults to 0). Must be non-negative.
        end_index: Zero-based index of the last entry to include (inclusive).
            Defaults to the last entry in the chain. Must be >= ``start_index``
            when supplied.

    Returns:
        A :class:`RangeVerificationResult` containing the verdict and both
        roots so a caller can report discrepancies.

    Raises:
        ValueError: if ``start_index`` is negative, ``end_index`` is less than
            ``start_index``, or the range falls outside the chain length.
        app.db.repositories.audit.AuditChainError: if the stored chain is
            broken or forked.
    """
    if start_index < 0:
        raise ValueError(f"start_index must be non-negative, got {start_index}.")

    chain = load_chain(session, document_id)
    chain_length = len(chain)

    if chain_length == 0:
        raise ValueError(
            f"Chain for document_id={document_id!r} has no entries; "
            "there is nothing to verify."
        )

    resolved_end = chain_length - 1 if end_index is None else end_index

    if end_index is not None and end_index < start_index:
        raise ValueError(
            f"end_index ({end_index}) must be >= start_index ({start_index})."
        )
    if resolved_end >= chain_length:
        raise ValueError(
            f"end_index ({resolved_end}) is out of range for a chain of "
            f"{chain_length} entries (max index {chain_length - 1})."
        )

    # The slice covers entries 0..resolved_end inclusive. The Merkle root
    # stored on entry at resolved_end was computed over exactly this prefix.
    prefix = chain[: resolved_end + 1]
    entry_payloads = [canonicalize(entry.payload) for entry in prefix]
    stored_root = chain[resolved_end].merkle_root_at_time

    result: VerificationResult = verify(entry_payloads, stored_root)

    return RangeVerificationResult(
        is_valid=result.is_valid,
        computed_root=result.computed_root,
        stored_root=stored_root,
        start_index=start_index,
        end_index=resolved_end,
        entry_count=len(prefix),
        document_id=document_id,
    )
