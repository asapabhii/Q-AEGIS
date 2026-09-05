"""Append and read the tamper-evident audit log, ``SPEC.md`` 3.8, ``PRD.md`` FR-7.

The hashing and tree construction here delegate entirely to
:mod:`app.audit.merkle`, whose ``build`` and ``verify`` stay pure. This module is
the side-effecting half: it decides what a chain is, what order its entries are
in, and how a new entry attaches to it.

There is no update and no delete function, and none may be added. The table
rejects both at the database level.
"""

import hashlib
import json
from typing import Any, Mapping, Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.audit.merkle import build, canonicalize
from app.db.models import AuditLog

#: Lock key for the chain holding events with no document.
#:
#: A literal string rather than a null, because the advisory lock function needs
#: something to hash and "all document-less events share one chain" is a real
#: statement about the data, not a fallback.
SYSTEM_CHAIN_KEY = "__system__"


class AuditChainError(RuntimeError):
    """Raised when the stored chain for one document is not a single chain.

    A broken or forked chain is a tampering indicator, not a routine error, so it
    surfaces as its own type rather than as a generic failure that a caller might
    reasonably retry. The ``no_forked_chain`` constraint on the table makes this
    unreachable through normal writes, which is exactly why hitting it is worth a
    distinct signal.
    """


def hash_payload(payload: Mapping[str, Any]) -> str:
    """Return the SHA-256 of ``payload``'s canonical serialisation.

    Plain SHA-256, not the leaf hash from :mod:`app.audit.merkle`. The two are
    deliberately different values with different jobs: this one is the row's
    ``payload_hash``, the content identity that the next row's ``prev_hash``
    points at, while the leaf hash carries RFC 6962 domain separation and exists
    only inside the tree.
    """
    return hashlib.sha256(canonicalize(payload)).hexdigest()


def normalize_payload(payload: Mapping[str, Any]) -> dict[str, Any]:
    """Round-trip ``payload`` through its canonical form before storage.

    This is not cosmetic, and removing it breaks verification. ``payload`` is
    stored as ``jsonb``, which normalises what it is given: it discards key
    order, collapses duplicate keys, and keeps numbers as ``numeric``. So the
    value read back later is not guaranteed to serialise to the same bytes as the
    value passed in, and a verifier recomputing the hash from the stored row
    would get a different digest for an untampered entry.

    Storing the parsed canonical form removes the gap: what lands in the column is
    derived from the exact bytes that were hashed, so re-canonicalising the row on
    the way out reproduces them.

    Constraint this places on callers, worth knowing before adding a field:
    payload values must be JSON primitives (``str``, ``int``, ``float``, ``bool``,
    ``None``) or containers of them. A ``Decimal``, a ``datetime``, or a ``UUID``
    raises here rather than being coerced, because a silent coercion is how two
    different values end up sharing a hash. Convert them at the call site, where
    the intended representation is known.
    """
    return json.loads(canonicalize(payload).decode("utf-8"))


def order_chain(
    entries: Sequence[AuditLog], *, document_id: UUID | None = None
) -> list[AuditLog]:
    """Order one chain's entries by following their ``prev_hash`` links.

    Pure: no I/O, no mutation of ``entries``. Separated from :func:`load_chain` so
    the tampering cases can be tested directly. The database's ``no_forked_chain``
    constraint makes a fork unreachable through any normal write, which is exactly
    why the check for one cannot be exercised by inserting rows.

    Order comes from the links, not from sorting by ``created_at``. That is
    deliberate: ``created_at`` defaults to ``now()``, which is transaction-scoped,
    so entries written in one transaction share a timestamp exactly and a
    timestamp sort would put them in an arbitrary order. The links are the
    authority on sequence, and they are also what a verifier checks.

    Args:
        entries: The chain's entries, in any order.
        document_id: Included in error messages only, to identify the chain.

    Returns:
        Entries from genesis to tail. Empty when ``entries`` is empty.

    Raises:
        AuditChainError: if the entries do not form exactly one unbroken chain.
    """
    if not entries:
        return []

    by_prev: dict[str | None, AuditLog] = {}
    for entry in entries:
        if entry.prev_hash in by_prev:
            raise AuditChainError(
                "Two audit entries claim the same predecessor for "
                f"document_id={document_id!r}. This is a forked chain."
            )
        by_prev[entry.prev_hash] = entry

    ordered: list[AuditLog] = []
    cursor: str | None = None
    while cursor in by_prev:
        entry = by_prev.pop(cursor)
        ordered.append(entry)
        cursor = entry.payload_hash

    if by_prev:
        raise AuditChainError(
            f"{len(by_prev)} audit entr(ies) for document_id={document_id!r} are "
            "not reachable from the genesis entry. The chain is broken."
        )
    return ordered


def load_chain(session: Session, document_id: UUID | None) -> list[AuditLog]:
    """Return one chain's entries in true chain order.

    Args:
        session: Active session.
        document_id: The document whose chain to load, or ``None`` for the system
            chain of events with no document.

    Returns:
        Entries from genesis to tail. Empty when the chain has no entries yet.

    Raises:
        AuditChainError: if the stored rows do not form exactly one unbroken
            chain, which is a tampering indicator rather than a routine error.
    """
    rows = list(session.scalars(_chain_query(document_id)).all())
    return order_chain(rows, document_id=document_id)


def current_root(session: Session, document_id: UUID | None) -> str:
    """Return the Merkle root over one chain as it currently stands.

    Recomputed from the stored payloads rather than read from the newest row's
    ``merkle_root_at_time``. Reading the stored value back would be trusting the
    system's own claim, which is the thing ``PRD.md`` FR-7 says an auditor must
    not have to do.
    """
    return build(_leaf_entries(load_chain(session, document_id))).root


def append_entry(
    session: Session,
    *,
    event_type: str,
    payload: Mapping[str, Any],
    document_id: UUID | None = None,
    actor_id: UUID | None = None,
) -> AuditLog:
    """Append one entry to a chain and return it, without committing.

    Does not commit on purpose. The caller's transaction is what makes "the
    decision and its audit entry are one atomic event" true; committing here
    would let a decision's own write roll back while its log entry survived.

    Args:
        session: Active session, inside a transaction.
        event_type: Event name. Use a value from
            :class:`app.db.enums.AuditEventType` unless adding a new one.
        payload: The event body. Must contain JSON primitives only; see
            :func:`normalize_payload`.
        document_id: Document this event concerns, or ``None`` for a system event.
        actor_id: Acting user, or ``None`` when no human triggered the event.

    Returns:
        The pending :class:`~app.db.models.AuditLog` row, flushed so its
        server-generated ``id`` is populated.
    """
    # Serialise appends to this one chain for the rest of the transaction.
    #
    # The no_forked_chain constraint is what actually guarantees correctness; this
    # lock only stops two concurrent writers from racing to build on the same
    # tail and one of them failing on that constraint. Transaction-scoped, so it
    # is released on commit or rollback with no unlock call to forget.
    lock_id = func.hashtextextended(_lock_key(document_id), 0)
    session.execute(select(func.pg_advisory_xact_lock(lock_id)))

    stored_payload = normalize_payload(payload)
    chain = load_chain(session, document_id)
    prev_hash = chain[-1].payload_hash if chain else None

    entry = AuditLog(
        document_id=document_id,
        actor_id=actor_id,
        event_type=event_type,
        payload=stored_payload,
        payload_hash=hash_payload(stored_payload),
        prev_hash=prev_hash,
        merkle_root_at_time=build(
            _leaf_entries(chain) + [canonicalize(stored_payload)]
        ).root,
    )
    session.add(entry)
    # Flush rather than commit: surfaces a constraint violation here, attributable
    # to this write, instead of at an unrelated commit later in the request.
    session.flush()
    return entry


def _chain_query(document_id: UUID | None):
    """Select every entry belonging to one chain."""
    statement = select(AuditLog)
    if document_id is None:
        return statement.where(AuditLog.document_id.is_(None))
    return statement.where(AuditLog.document_id == document_id)


def _lock_key(document_id: UUID | None) -> str:
    """Return the advisory-lock key identifying one chain."""
    return SYSTEM_CHAIN_KEY if document_id is None else str(document_id)


def _leaf_entries(chain: list[AuditLog]) -> list[bytes]:
    """Re-canonicalise stored payloads into Merkle leaf inputs."""
    return [canonicalize(entry.payload) for entry in chain]
