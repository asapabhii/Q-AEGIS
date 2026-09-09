"""Audit log service layer, ``SPEC.md`` 3.8, ``PRD.md`` FR-7.

This module provides independent verification of the audit log chain. The
verification implemented here recomputes the Merkle root from stored payloads
and compares it against the value recorded at write time. It does NOT consult
any stored "valid" flag or any value this system set at write time — the root
is recomputed entirely from the payloads themselves.

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
from uuid import UUID

from sqlalchemy.orm import Session

from app.audit.merkle import VerificationResult, canonicalize, verify
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
