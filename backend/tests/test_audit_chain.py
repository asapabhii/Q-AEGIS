"""The audit log's chain and root behavior, ``SPEC.md`` 3.8, ``PRD.md`` FR-7.

:mod:`app.audit.merkle` is tested separately as pure functions. What is tested
here is the part that touches the database: what a chain is, how an entry attaches
to one, and whether the stored payload can still be re-verified after a round trip
through ``jsonb``.
"""

import json
from datetime import datetime, timezone
from decimal import Decimal
from uuid import UUID, uuid4

import psycopg
import pytest
from sqlalchemy import event, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.audit.merkle import (
    EMPTY_ROOT,
    build,
    canonicalize,
    frontier_from_json,
    root_of,
    verify,
)
from app.db.enums import AuditEventType, UserRole
from app.db.models import AuditLog, Document
from app.db.repositories import audit as audit_repo
from app.db.repositories import documents as documents_repo
from tests.test_db_append_only import statement_expected_to_fail

EVENT = AuditEventType.CLASSIFICATION_COMPLETED.value


def append(
    session: Session, document_id: UUID | None, note: str, **kwargs: object
) -> object:
    """Append an entry with a distinguishable payload."""
    return audit_repo.append_entry(
        session,
        event_type=EVENT,
        document_id=document_id,
        payload={"note": note},
        **kwargs,
    )


def insert_raw_entry(
    session: Session,
    *,
    document_id: UUID | None,
    prev_hash: str | None,
    payload: dict[str, object] | None = None,
    frontier: list[object] | None = None,
) -> None:
    """Insert an entry with raw SQL, bypassing the repository's chain logic.

    Needed to construct states the repository will not produce, which is the only
    way to test that the database rejects them rather than trusting Python to
    never ask.
    """
    body = payload if payload is not None else {"note": "raw"}
    session.execute(
        text(
            "INSERT INTO audit_log "
            "(document_id, event_type, payload, payload_hash, prev_hash, "
            " merkle_root_at_time, frontier) "
            "VALUES (:document_id, :event_type, CAST(:payload AS jsonb), "
            "        :payload_hash, :prev_hash, :root, CAST(:frontier AS jsonb))"
        ),
        {
            "document_id": document_id,
            "event_type": EVENT,
            "payload": json.dumps(body),
            "payload_hash": audit_repo.hash_payload(body),
            "prev_hash": prev_hash,
            "root": EMPTY_ROOT,
            # Defaults to an empty frontier regardless of what precedes this row.
            # These inserts exist to build states the repository refuses to
            # produce, so a frontier consistent with the chain would be a
            # contradiction. Pass one explicitly only when it is what is under
            # test.
            "frontier": json.dumps([] if frontier is None else frontier),
        },
    )


# --------------------------------------------------------------------------
# Chain construction
# --------------------------------------------------------------------------


def test_the_first_entry_for_a_document_has_no_predecessor(
    db_session: Session, registered_document: Document
) -> None:
    """Genesis carries a null ``prev_hash``, not a sentinel of 64 zeros."""
    entry = append(db_session, registered_document.id, "first")
    assert entry.prev_hash is None


def test_each_entry_links_to_the_previous_one(
    db_session: Session, registered_document: Document
) -> None:
    """``prev_hash`` is the preceding entry's ``payload_hash``."""
    first = append(db_session, registered_document.id, "first")
    second = append(db_session, registered_document.id, "second")
    third = append(db_session, registered_document.id, "third")

    assert second.prev_hash == first.payload_hash
    assert third.prev_hash == second.payload_hash


def test_chains_are_per_document(
    db_session: Session, registered_document: Document, seeded_users: dict
) -> None:
    """One document's entries never link into another's.

    A single global chain would serialise every write in the system behind one
    row, and one document's history would depend on unrelated documents' entries.
    """
    other = documents_repo.register_document(
        db_session,
        uploaded_by=seeded_users[UserRole.DATA_OWNER].id,
        filename="other.pdf",
    )

    first_a = append(db_session, registered_document.id, "a1")
    first_b = append(db_session, other.id, "b1")
    second_a = append(db_session, registered_document.id, "a2")

    assert first_b.prev_hash is None
    assert second_a.prev_hash == first_a.payload_hash
    assert [e.payload["note"] for e in audit_repo.load_chain(db_session, other.id)] == [
        "b1"
    ]


def test_events_with_no_document_form_their_own_chain(db_session: Session) -> None:
    """A policy rule being created has no document, and still needs an entry."""
    first = append(db_session, None, "system-1")
    second = append(db_session, None, "system-2")

    assert first.prev_hash is None
    assert second.prev_hash == first.payload_hash
    assert len(audit_repo.load_chain(db_session, None)) == 2


def test_load_chain_returns_entries_in_link_order(
    db_session: Session, registered_document: Document
) -> None:
    """Order comes from the links, not from ``created_at``.

    All three entries here are written in one transaction, so ``now()`` gives them
    an identical timestamp. A timestamp sort would order them arbitrarily; this
    asserts the links are what decide.
    """
    for note in ("one", "two", "three"):
        append(db_session, registered_document.id, note)

    chain = audit_repo.load_chain(db_session, registered_document.id)
    assert [entry.payload["note"] for entry in chain] == ["one", "two", "three"]

    timestamps = {entry.created_at for entry in chain}
    assert len(timestamps) == 1, "expected one transaction timestamp for all entries"


def test_load_chain_is_empty_for_a_document_with_no_entries(
    db_session: Session, registered_document: Document
) -> None:
    """An empty chain is a valid state, not an error."""
    assert audit_repo.load_chain(db_session, registered_document.id) == []


def test_actor_is_recorded_when_one_acted(
    db_session: Session, registered_document: Document, seeded_users: dict
) -> None:
    """``PRD.md`` FR-15's audit viewer shows an actor, so one has to be stored."""
    actor = seeded_users[UserRole.SECURITY_ANALYST]
    entry = append(db_session, registered_document.id, "acted", actor_id=actor.id)
    assert entry.actor_id == actor.id


def test_actor_is_null_for_a_system_event(
    db_session: Session, registered_document: Document
) -> None:
    """A scheduled recomputation has no human actor, and must not invent one."""
    assert append(db_session, registered_document.id, "scheduled").actor_id is None


# --------------------------------------------------------------------------
# Merkle root
# --------------------------------------------------------------------------


def test_stored_root_matches_a_root_recomputed_from_the_payloads(
    db_session: Session, registered_document: Document
) -> None:
    """The root written with an entry is the root of the chain including it."""
    append(db_session, registered_document.id, "one")
    append(db_session, registered_document.id, "two")
    latest = append(db_session, registered_document.id, "three")

    chain = audit_repo.load_chain(db_session, registered_document.id)
    expected = build([canonicalize(entry.payload) for entry in chain]).root

    assert latest.merkle_root_at_time == expected


def test_each_entry_moves_the_root(
    db_session: Session, registered_document: Document
) -> None:
    """A root that did not change would not be committing to the new entry."""
    roots = [
        append(db_session, registered_document.id, note).merkle_root_at_time
        for note in ("one", "two", "three")
    ]
    assert len(set(roots)) == 3


def test_current_root_of_an_empty_chain_is_the_empty_root(
    db_session: Session, registered_document: Document
) -> None:
    """ "The log is empty" is itself a verifiable claim."""
    assert audit_repo.current_root(db_session, registered_document.id) == EMPTY_ROOT


def test_a_stored_chain_verifies_against_its_stored_root(
    db_session: Session, registered_document: Document
) -> None:
    """The end-to-end property FR-7 exists for.

    An auditor exports the entries, recomputes the root with the pure verifier,
    and compares it against the root the system recorded. This is that, with no
    stored "valid" flag consulted anywhere.
    """
    for note in ("alpha", "beta", "gamma", "delta", "epsilon"):
        append(db_session, registered_document.id, note)

    chain = audit_repo.load_chain(db_session, registered_document.id)
    result = verify(
        [canonicalize(entry.payload) for entry in chain],
        chain[-1].merkle_root_at_time,
    )
    assert result.is_valid
    assert result.leaf_count == 5


def test_an_odd_length_chain_verifies(
    db_session: Session, registered_document: Document
) -> None:
    """Odd leaf counts are the case the promote-not-duplicate rule exists for."""
    for note in ("one", "two", "three"):
        append(db_session, registered_document.id, note)

    chain = audit_repo.load_chain(db_session, registered_document.id)
    assert verify(
        [canonicalize(entry.payload) for entry in chain],
        chain[-1].merkle_root_at_time,
    ).is_valid


def test_a_tampered_stored_payload_fails_verification(
    db_session: Session, registered_document: Document
) -> None:
    """The whole point: an altered entry is detectable after the fact.

    The alteration is simulated in memory rather than with an UPDATE, because the
    trigger refuses the UPDATE outright, which is a different guarantee tested in
    ``test_db_append_only.py``. Both matter: one stops the edit, this one catches
    it if the first were ever bypassed.
    """
    for note in ("one", "two", "three"):
        append(db_session, registered_document.id, note)

    chain = audit_repo.load_chain(db_session, registered_document.id)
    entries = [canonicalize(entry.payload) for entry in chain]
    entries[1] = canonicalize({"note": "two-but-altered"})

    assert not verify(entries, chain[-1].merkle_root_at_time).is_valid


# --------------------------------------------------------------------------
# Payload storage and round-tripping
# --------------------------------------------------------------------------


def test_payload_hash_matches_the_stored_payload(
    db_session: Session, registered_document: Document
) -> None:
    """A hash whose payload cannot be rehashed proves nothing."""
    entry = append(db_session, registered_document.id, "checkable")
    db_session.expire(entry)
    assert audit_repo.hash_payload(entry.payload) == entry.payload_hash


@pytest.mark.parametrize(
    "payload",
    [
        {"text": "plain"},
        {"unicode": "café, 名前, emoji ok"},
        {"nested": {"b": 1, "a": [1, 2, {"deep": True}]}},
        {"float": 0.6667, "int": 42, "bool": False, "none": None},
        {"zzz": 1, "aaa": 2, "mmm": 3},
        {"empty_list": [], "empty_dict": {}, "empty_string": ""},
        {"big_int": 2**53, "small_float": 1e-07, "negative": -0.5},
    ],
    ids=[
        "plain",
        "unicode",
        "nested",
        "mixed-primitives",
        "unsorted-keys",
        "empty-containers",
        "numeric-edges",
    ],
)
def test_payloads_survive_a_jsonb_round_trip_byte_for_byte(
    db_session: Session, registered_document: Document, payload: dict
) -> None:
    """Verification depends on this, so it is tested per payload shape.

    ``jsonb`` discards key order and stores numbers as ``numeric``, so a payload
    written naively can come back serialising to different bytes than went in, and
    an untampered entry would then fail verification. The repository normalises
    through the canonical form before storing to close that gap; these cases are
    the ones most likely to reopen it.
    """
    entry = audit_repo.append_entry(
        db_session,
        event_type=EVENT,
        document_id=registered_document.id,
        payload=payload,
    )
    expected_hash = entry.payload_hash

    db_session.expire(entry)
    reloaded = db_session.get(type(entry), entry.id)

    assert audit_repo.hash_payload(reloaded.payload) == expected_hash


@pytest.mark.parametrize(
    "payload",
    [
        {"amount": Decimal("1.5")},
        {"when": datetime(2026, 9, 5, tzinfo=timezone.utc)},
        {"who": uuid4()},
        {"what": {1, 2, 3}},
    ],
    ids=["decimal", "datetime", "uuid", "set"],
)
def test_non_json_payload_values_are_refused_rather_than_coerced(
    db_session: Session, registered_document: Document, payload: dict
) -> None:
    """A silent coercion is how two different values end up sharing a hash.

    Each of these has an obvious-looking string form, which is exactly the
    problem: two distinct values can render identically, and the call site is
    where the intended representation is actually known.
    """
    with pytest.raises(TypeError):
        audit_repo.append_entry(
            db_session,
            event_type=EVENT,
            document_id=registered_document.id,
            payload=payload,
        )


# --------------------------------------------------------------------------
# Fork prevention
# --------------------------------------------------------------------------


def test_two_entries_cannot_claim_the_same_predecessor(
    db_session: Session, registered_document: Document
) -> None:
    """That is what a fork is, and the constraint rejects it outright."""
    genesis = append(db_session, registered_document.id, "genesis")
    append(db_session, registered_document.id, "real-second")

    with statement_expected_to_fail(db_session):
        with pytest.raises(IntegrityError) as exc_info:
            insert_raw_entry(
                db_session,
                document_id=registered_document.id,
                prev_hash=genesis.payload_hash,
                payload={"note": "forked-second"},
            )

    assert isinstance(exc_info.value.orig, psycopg.errors.UniqueViolation)


def test_a_document_cannot_have_two_genesis_entries(
    db_session: Session, registered_document: Document
) -> None:
    """Requires ``NULLS NOT DISTINCT``.

    Postgres treats each null as unique by default, so without it two entries with
    a null ``prev_hash`` would both be accepted and the chain would have two
    beginnings.
    """
    append(db_session, registered_document.id, "genesis")

    with statement_expected_to_fail(db_session):
        with pytest.raises(IntegrityError) as exc_info:
            insert_raw_entry(
                db_session, document_id=registered_document.id, prev_hash=None
            )

    assert isinstance(exc_info.value.orig, psycopg.errors.UniqueViolation)


def test_the_same_predecessor_is_allowed_across_different_chains(
    db_session: Session, registered_document: Document, seeded_users: dict
) -> None:
    """The constraint is scoped per chain, so unrelated documents don't collide.

    Both documents' genesis entries have a null ``prev_hash``, which must remain
    legal, or registering a second document would fail.
    """
    other = documents_repo.register_document(
        db_session,
        uploaded_by=seeded_users[UserRole.DATA_OWNER].id,
        filename="second.pdf",
    )
    assert append(db_session, registered_document.id, "x").prev_hash is None
    assert append(db_session, other.id, "y").prev_hash is None


# --------------------------------------------------------------------------
# Broken chain detection
# --------------------------------------------------------------------------


def test_an_unreachable_entry_is_reported_as_a_broken_chain(
    db_session: Session, registered_document: Document
) -> None:
    """An entry pointing at a predecessor that does not exist is not skipped.

    Silently dropping it from the chain would hide a tampering indicator, so
    reading the chain fails instead.
    """
    append(db_session, registered_document.id, "genesis")
    insert_raw_entry(
        db_session, document_id=registered_document.id, prev_hash="ff" * 32
    )

    with pytest.raises(audit_repo.AuditChainError, match="not reachable"):
        audit_repo.load_chain(db_session, registered_document.id)


# --------------------------------------------------------------------------
# The append path carries the frontier instead of rereading the chain
#
# app.audit.merkle already asserts the incremental root equals a full rebuild as a
# pure property. What these add is that the stored column still agrees with an
# independent recomputation from the stored payloads after a real round trip
# through jsonb, and that a write's cost stops growing with the chain.
# --------------------------------------------------------------------------


def test_stored_roots_agree_with_independent_recomputation(
    db_session: Session, registered_document: Document
) -> None:
    """Every row's stored root matches one rebuilt from the payloads before it.

    The write path carries an O(log n) frontier forward; the verification path
    rehashes every stored payload. This is the test that keeps the fast path
    honest, and it checks every prefix rather than only the final root, so a
    divergence cannot hide behind a later append that happens to agree.
    """
    for index in range(12):
        append(db_session, registered_document.id, f"entry-{index}")

    chain = audit_repo.load_chain(db_session, registered_document.id)

    for length in range(1, len(chain) + 1):
        rebuilt = build([canonicalize(e.payload) for e in chain[:length]]).root
        assert chain[length - 1].merkle_root_at_time == rebuilt


def test_the_newest_stored_root_is_the_current_root(
    db_session: Session, registered_document: Document
) -> None:
    """``current_root`` recomputes, and lands on what the tail already stored."""
    for index in range(7):
        append(db_session, registered_document.id, f"entry-{index}")

    chain = audit_repo.load_chain(db_session, registered_document.id)
    assert audit_repo.current_root(db_session, registered_document.id) == (
        chain[-1].merkle_root_at_time
    )


def test_a_stored_frontier_round_trips_through_jsonb(
    db_session: Session, registered_document: Document
) -> None:
    """The frontier has to survive Postgres, or the next append computes nonsense."""
    for index in range(11):
        append(db_session, registered_document.id, f"entry-{index}")

    tail = audit_repo.load_chain(db_session, registered_document.id)[-1]
    frontier = frontier_from_json(tail.frontier)

    assert frontier.leaf_count == 11
    assert [subtree.size for subtree in frontier.subtrees] == [8, 2, 1]
    assert root_of(frontier) == tail.merkle_root_at_time


def test_an_append_never_reads_the_whole_chain(
    db_session: Session, registered_document: Document
) -> None:
    """Every ``audit_log`` read an append performs is bounded, whatever the length.

    The regression this guards against is the one review caught: computing a root
    by rereading the chain costs O(n) per append and O(n^2) over a chain's life, on
    the write path every decision in the system goes through.

    It asserts on the shape of the SQL rather than on a statement count, because
    the old code read the chain in a single unbounded query, so counting statements
    would have passed while the cost was still linear. A row count or a timing
    assertion would be flakier in CI than this is.
    """
    for index in range(25):
        append(db_session, registered_document.id, f"filler-{index}")

    statements: list[str] = []
    engine = db_session.get_bind()

    def record(conn, cursor, statement, parameters, context, executemany) -> None:
        statements.append(" ".join(statement.split()))

    event.listen(engine, "before_cursor_execute", record)
    try:
        append(db_session, registered_document.id, "the-one-under-test")
    finally:
        event.remove(engine, "before_cursor_execute", record)

    reads = [
        statement
        for statement in statements
        if statement.upper().startswith("SELECT") and "audit_log" in statement
    ]
    assert reads, "expected the append to read the chain tail"
    for statement in reads:
        assert "LIMIT" in statement.upper(), (
            "an unbounded read of audit_log during an append means the write path "
            f"is O(n) again: {statement}"
        )


def test_appending_to_an_ambiguous_chain_is_refused(
    db_session: Session, registered_document: Document
) -> None:
    """More than one tail means the chain is not one chain, so the append refuses.

    The shape planted here is an injected orphan: an entry whose ``prev_hash``
    names a row that does not exist. That leaves two entries nothing builds on, so
    "what does the next entry attach to" has no single answer. Note it does not
    violate ``no_forked_chain``, since the two have different predecessors, which
    is why the check is worth having on top of the constraint.

    Without it an append would pick one arbitrarily and bury the tampering under
    entries that each look valid.
    """
    append(db_session, registered_document.id, "genesis")
    insert_raw_entry(
        db_session,
        document_id=registered_document.id,
        prev_hash="ab" * 32,
        payload={"note": "orphan"},
    )

    with pytest.raises(audit_repo.AuditChainError, match="more than one tail"):
        append(db_session, registered_document.id, "next")


def test_an_ambiguous_system_chain_is_refused_too(db_session: Session) -> None:
    """The null-document chain gets the same check, not a weaker one.

    Worth asserting separately because the tail query branches on whether
    ``document_id`` is null, so the system chain runs different SQL. It is also the
    chain with no natural bound, since every document-less event in the system
    lands in it.
    """
    append(db_session, None, "system-genesis")
    insert_raw_entry(
        db_session,
        document_id=None,
        prev_hash="cd" * 32,
        payload={"note": "system-orphan"},
    )

    with pytest.raises(audit_repo.AuditChainError, match="more than one tail"):
        append(db_session, None, "next")


def test_a_tampered_stored_frontier_is_refused_on_the_next_append(
    db_session: Session, registered_document: Document
) -> None:
    """A frontier is validated when read back, not trusted.

    Left unchecked, a malformed frontier on the tail would produce a plausible but
    wrong root for this entry and every entry after it, and the log would look
    internally consistent while committing to nothing.
    """
    insert_raw_entry(
        db_session,
        document_id=registered_document.id,
        prev_hash=None,
        # 3 is not a power of two, so no complete subtree has that many leaves and
        # extend_frontier could not have produced this. Planted with an INSERT
        # because audit_log rejects UPDATE, which is the point of the table.
        frontier=[[3, "aa" * 32]],
    )

    with pytest.raises(ValueError, match="power of two"):
        append(db_session, registered_document.id, "next")


def test_ordering_refuses_a_forked_chain() -> None:
    """Two entries claiming one predecessor is refused when reading, too.

    The ``no_forked_chain`` constraint makes this unreachable through any normal
    write, which is why it is tested against the pure ordering function rather
    than by inserting rows: the reader must not silently pick a branch if the
    constraint were ever dropped or if entries arrived from an export.
    """
    forked = [
        AuditLog(
            document_id=None,
            event_type=EVENT,
            payload={"note": "a"},
            payload_hash="aa" * 32,
            prev_hash=None,
            merkle_root_at_time=EMPTY_ROOT,
        ),
        AuditLog(
            document_id=None,
            event_type=EVENT,
            payload={"note": "b"},
            payload_hash="bb" * 32,
            prev_hash=None,
            merkle_root_at_time=EMPTY_ROOT,
        ),
    ]

    with pytest.raises(audit_repo.AuditChainError, match="forked chain"):
        audit_repo.order_chain(forked)


def test_ordering_an_empty_chain_returns_nothing() -> None:
    """No entries is a valid state for the pure ordering function too."""
    assert audit_repo.order_chain([]) == []


def test_a_chain_with_no_genesis_is_reported_as_broken(
    db_session: Session, registered_document: Document
) -> None:
    """Every chain must have a beginning; entries with none are unverifiable."""
    insert_raw_entry(
        db_session, document_id=registered_document.id, prev_hash="ab" * 32
    )

    with pytest.raises(audit_repo.AuditChainError):
        audit_repo.load_chain(db_session, registered_document.id)
