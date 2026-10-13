"""Append and read the tamper-evident audit log, ``SPEC.md`` 3.8, ``PRD.md`` FR-7.

The hashing and tree construction here delegate entirely to
:mod:`app.audit.merkle`, whose ``build`` and ``verify`` stay pure. This module is
the side-effecting half: it decides what a chain is, what order its entries are
in, and how a new entry attaches to it.

There is no update and no delete function, and none may be added. The table
rejects both at the database level.

Reading and appending deliberately take different routes to a root.
:func:`append_entry` carries the O(log n) Merkle frontier forward from the tail
row, so a write reads one entry rather than the whole chain. :func:`current_root`
and :func:`load_chain` rehash every stored payload instead, because a verifier
must not have to trust state this system wrote. The write path is fast, the read
path is independent, and a test asserts they agree.
"""

import hashlib
import json
from typing import Any, Mapping, Sequence
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session, aliased

from app.audit.merkle import (
    EMPTY_FRONTIER,
    build,
    canonicalize,
    extend_frontier,
    frontier_from_json,
    frontier_to_json,
    root_of,
)
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


class DuplicateAuditPayloadError(AuditChainError):
    """Raised when an append would repeat a payload already on the same chain.

    The chain links each entry to the one before it by ``payload_hash`` (the next
    row's ``prev_hash`` names it). Two entries on one chain with a byte-identical
    payload therefore share a ``payload_hash``, and "which entry does the next one
    build on" stops having a single answer: tail-finding
    (:func:`_chain_tail`) sees both as built-on and returns ``None``, so every
    later append is computed as a second genesis and collides on
    ``no_forked_chain``. One deterministic event type is enough to wedge a whole
    chain this way, and the failure surfaces far from its cause.

    So the append path refuses a duplicate up front, attributably: every audit
    payload must be intrinsically distinct. Where an event could otherwise repeat
    (a ranking run with no candidates, a re-seed of a fixed demo graph), the call
    site carries a unique element — see ``migration_audit_payload``'s
    ``ranking_run_id`` and ``graph.seed``'s ``seed_run_id``. This is the mechanical
    enforcement of that convention, not a substitute for it: it converts a silent,
    chain-corrupting collision into a loud error naming the offending event.
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
    canonical = canonicalize(stored_payload)
    payload_hash = hash_payload(stored_payload)

    # Refuse a payload already present on this chain, before touching the tail or
    # the frontier. A duplicate payload_hash makes the prev_hash links ambiguous
    # and silently wedges every later append (see DuplicateAuditPayloadError); a
    # bounded lookup here turns that into a loud, attributable failure at the
    # write that introduced it. The advisory lock taken above serialises appends
    # to this chain, so the check and the insert cannot race. .limit(1) keeps the
    # read bounded — an unbounded scan here would make the write path O(n).
    if _payload_already_on_chain(session, document_id, payload_hash):
        raise DuplicateAuditPayloadError(
            f"Refusing to append event {event_type!r} to the chain for "
            f"document_id={document_id!r}: a byte-identical payload is already "
            "recorded on it, so the two would share a payload_hash and make the "
            "chain's prev_hash links ambiguous. Every audit payload must be "
            "intrinsically distinct; give this event a unique element (a per-run "
            "id or timestamp), as migration_audit_payload and graph.seed do."
        )

    tail = _chain_tail(session, document_id)

    if tail is None:
        prev_hash, frontier = None, EMPTY_FRONTIER
    else:
        prev_hash = tail.payload_hash
        frontier = frontier_from_json(tail.frontier)

    extended = extend_frontier(frontier, canonical)

    entry = AuditLog(
        document_id=document_id,
        actor_id=actor_id,
        event_type=event_type,
        payload=stored_payload,
        payload_hash=payload_hash,
        prev_hash=prev_hash,
        merkle_root_at_time=root_of(extended),
        frontier=frontier_to_json(extended),
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


def _payload_already_on_chain(
    session: Session, document_id: UUID | None, payload_hash: str
) -> bool:
    """Whether an entry with ``payload_hash`` is already on this chain.

    A bounded lookup (``LIMIT 1``): existence is all the append path needs, and an
    unbounded read of ``audit_log`` on every write would make appending O(n) in
    the chain length. Filtered to the one chain via ``document_id`` so a hash that
    legitimately recurs on a *different* document's chain is not treated as a
    collision — only a repeat within a single chain breaks that chain's links.
    """
    found = session.scalar(
        _chain_query(document_id)
        .where(AuditLog.payload_hash == payload_hash)
        .limit(1)
    )
    return found is not None


def _chain_tail(session: Session, document_id: UUID | None) -> AuditLog | None:
    """Return the entry nothing else builds on, or ``None`` for an empty chain.

    The tail is found by its defining property rather than by sorting: it is the
    one entry whose ``payload_hash`` no other entry in the chain claims as its
    ``prev_hash``. Ordering by ``created_at`` would not work, since that column
    defaults to a transaction-scoped ``now()`` and entries written together share
    it exactly.

    The ``no_forked_chain`` index on ``(document_id, prev_hash)`` serves the
    correlated subquery, so this is a constant number of indexed lookups no matter
    how long the chain is.

    Raises:
        AuditChainError: if more than one tail exists, meaning "what does the next
            entry attach to" has no single answer. ``no_forked_chain`` already
            refuses two entries sharing a predecessor, but it cannot refuse an
            injected entry whose ``prev_hash`` names a row that does not exist,
            and that leaves two entries nothing builds on. Refusing to extend a
            chain in that state stops the tampering being buried under later
            entries that each look valid on their own.
    """
    successor = aliased(AuditLog, name="successor")
    builds_on_it = (
        select(1)
        .where(successor.prev_hash == AuditLog.payload_hash)
        .where(
            successor.document_id.is_(None)
            if document_id is None
            else successor.document_id == document_id
        )
        .exists()
    )

    tails = list(
        session.scalars(_chain_query(document_id).where(~builds_on_it).limit(2)).all()
    )

    if len(tails) > 1:
        raise AuditChainError(
            f"Chain for document_id={document_id!r} has more than one tail, so "
            "there is no single entry to append after. The chain is broken."
        )
    return tails[0] if tails else None


def _lock_key(document_id: UUID | None) -> str:
    """Return the advisory-lock key identifying one chain."""
    return SYSTEM_CHAIN_KEY if document_id is None else str(document_id)


def _leaf_entries(chain: list[AuditLog]) -> list[bytes]:
    """Re-canonicalise stored payloads into Merkle leaf inputs."""
    return [canonicalize(entry.payload) for entry in chain]
