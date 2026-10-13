"""Service-level tests for audit log verification, ``SPEC.md`` 3.8, ``PRD.md`` FR-7.

Pure-function tamper detection (altered entry, odd leaf count, reordering,
insertion, truncation) is already covered in ``test_merkle.py``. Database-level
chain integrity (trigger, fork constraint, broken chain) is covered in
``test_audit_chain.py``. What this file adds is the service layer:

1. Verification that ignores any stored flag and recomputes from payloads.
2. Prefix verification through ``end_index`` (a stored root on entry N covers
   ``0..N``, so there is no ``start_index``).
3. Role check refusing roles that are not permitted to verify.

Never add UPDATE or DELETE against ``audit_log``, and do not add a parallel
append path. All writes here go through
:func:`app.db.repositories.audit.append_entry`.
"""

from types import SimpleNamespace
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.audit import service as audit_service
from app.audit.merkle import (
    build,
    canonicalize,
    hash_leaf,
    verify_consistency,
    verify_inclusion,
)
from app.audit.service import (
    build_consistency_proof,
    build_inclusion_proof,
    verify_chain_range,
)
from app.db.enums import AuditEventType, UserRole
from app.db.models import Document
from app.db.repositories import audit as audit_repo

EVENT = AuditEventType.CLASSIFICATION_COMPLETED.value

VERIFY_URL = "/api/v1/audit/verify"
ENTRIES_URL = "/api/v1/audit/entries"
INCLUSION_URL = "/api/v1/audit/inclusion-proof"
CONSISTENCY_URL = "/api/v1/audit/consistency-proof"
ROLE_HEADER = "X-Q-AEGIS-Actor-Role"


def append(session: Session, document_id: UUID | None, note: str) -> object:
    """Append one entry with a distinguishable payload."""
    return audit_repo.append_entry(
        session,
        event_type=EVENT,
        document_id=document_id,
        payload={"note": note},
    )


# ---------------------------------------------------------------------------
# verify_chain_range: independent recomputation, no stored-flag trust
# ---------------------------------------------------------------------------


def test_verify_chain_range_passes_clean_chain(
    db_session: Session, registered_document: Document
) -> None:
    """Recomputed root matches stored root for an untampered chain.

    No stored "valid" flag is consulted. The result comes entirely from
    recomputing the Merkle root over the stored payloads.
    """
    for note in ("alpha", "beta", "gamma", "delta", "epsilon"):
        append(db_session, registered_document.id, note)

    result = verify_chain_range(db_session, registered_document.id)

    assert result.is_valid
    assert result.computed_root == result.stored_root
    assert result.entry_count == 5
    assert result.document_id == registered_document.id


def test_verify_chain_range_detects_tampered_payload(
    db_session: Session, registered_document: Document, monkeypatch: pytest.MonkeyPatch
) -> None:
    """verify_chain_range itself flags a mutated payload, not just merkle.verify.

    The trigger refuses UPDATE, so the mutation is injected through the
    load_chain seam the service actually calls. Copies, not live ORM rows:
    dirtying a mapped instance would flush an UPDATE and abort the test on
    the trigger rather than on the service.
    """
    for note in ("one", "two", "three"):
        append(db_session, registered_document.id, note)

    real_chain = audit_repo.load_chain(db_session, registered_document.id)
    tampered = [
        SimpleNamespace(
            payload=({"note": "two-but-altered"} if i == 1 else dict(entry.payload)),
            merkle_root_at_time=entry.merkle_root_at_time,
        )
        for i, entry in enumerate(real_chain)
    ]
    monkeypatch.setattr(audit_service, "load_chain", lambda session, doc_id: tampered)

    result = verify_chain_range(db_session, registered_document.id)

    assert not result.is_valid
    assert result.computed_root != result.stored_root


def test_verify_chain_range_prefix_through_end_index(
    db_session: Session, registered_document: Document
) -> None:
    """end_index cuts a prefix from genesis, which is what the stored root covers."""
    for note in ("a", "b", "c", "d", "e", "f"):
        append(db_session, registered_document.id, note)

    result = verify_chain_range(db_session, registered_document.id, end_index=3)

    assert result.is_valid
    assert result.entry_count == 4
    assert result.end_index == 3
    assert not hasattr(result, "start_index")


def test_verify_chain_range_end_index_default_is_chain_tail(
    db_session: Session, registered_document: Document
) -> None:
    """Omitting end_index defaults to the last entry in the chain."""
    for note in ("x", "y", "z"):
        append(db_session, registered_document.id, note)

    result = verify_chain_range(db_session, registered_document.id)

    assert result.end_index == 2  # three entries, last index is 2
    assert result.entry_count == 3


def test_verify_chain_range_odd_entry_count(
    db_session: Session, registered_document: Document
) -> None:
    """An odd number of entries verifies correctly (the promote-not-duplicate rule)."""
    for note in ("p", "q", "r", "s", "t"):  # five entries
        append(db_session, registered_document.id, note)

    result = verify_chain_range(db_session, registered_document.id)

    assert result.is_valid
    assert result.entry_count == 5


def test_verify_chain_range_empty_chain(
    db_session: Session, registered_document: Document
) -> None:
    """An empty chain raises ValueError because there is no entry to index into."""
    with pytest.raises(ValueError):
        verify_chain_range(db_session, registered_document.id)


def test_verify_chain_range_negative_end_index_is_rejected(
    db_session: Session, registered_document: Document
) -> None:
    """Negative end_index is always invalid."""
    append(db_session, registered_document.id, "only")
    with pytest.raises(ValueError, match="non-negative"):
        verify_chain_range(db_session, registered_document.id, end_index=-1)


def test_verify_chain_range_out_of_bounds_end_index_is_rejected(
    db_session: Session, registered_document: Document
) -> None:
    """end_index beyond the chain length is a caller error."""
    append(db_session, registered_document.id, "only")
    with pytest.raises(ValueError, match="out of range"):
        verify_chain_range(db_session, registered_document.id, end_index=99)


# ---------------------------------------------------------------------------
# API endpoint: role checks
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "role",
    [UserRole.AUDITOR, UserRole.SECURITY_ADMIN, UserRole.SECURITY_ANALYST],
)
def test_verify_endpoint_admits_permitted_roles(
    client: TestClient,
    registered_document: Document,
    db_session: Session,
    role: UserRole,
) -> None:
    """Auditor, security_admin, and security_analyst are admitted."""
    for note in ("one", "two", "three"):
        append(db_session, registered_document.id, note)

    response = client.get(
        VERIFY_URL,
        params={"document_id": str(registered_document.id)},
        headers={ROLE_HEADER: role.value},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_valid"] is True
    assert data["entry_count"] == 3


@pytest.mark.parametrize(
    "role",
    [
        UserRole.DATA_OWNER,
        UserRole.COMPLIANCE_OFFICER,
        UserRole.CISO,
        UserRole.ENGINEER,
    ],
)
def test_verify_endpoint_refuses_excluded_roles(
    client: TestClient,
    registered_document: Document,
    role: UserRole,
) -> None:
    """Roles outside the auditor/admin/analyst set must be refused with 403."""
    response = client.get(
        VERIFY_URL,
        params={"document_id": str(registered_document.id)},
        headers={ROLE_HEADER: role.value},
    )
    assert response.status_code == 403


def test_verify_endpoint_refuses_missing_role_header(
    client: TestClient, registered_document: Document
) -> None:
    """A missing role header returns 401 before any database access."""
    response = client.get(
        VERIFY_URL,
        params={"document_id": str(registered_document.id)},
    )
    assert response.status_code == 401


def test_verify_endpoint_refuses_unrecognized_role(
    client: TestClient, registered_document: Document
) -> None:
    """An unrecognized role value returns 403."""
    response = client.get(
        VERIFY_URL,
        params={"document_id": str(registered_document.id)},
        headers={ROLE_HEADER: "superadmin"},
    )
    assert response.status_code == 403


def test_verify_endpoint_mid_chain_slice(
    client: TestClient,
    registered_document: Document,
    db_session: Session,
) -> None:
    """end_index can be supplied to verify a prefix slice via the API."""
    for note in ("a", "b", "c", "d", "e"):
        append(db_session, registered_document.id, note)

    response = client.get(
        VERIFY_URL,
        params={"document_id": str(registered_document.id), "end_index": 2},
        headers={ROLE_HEADER: UserRole.AUDITOR.value},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_valid"] is True
    assert data["entry_count"] == 3
    assert data["end_index"] == 2
    assert "start_index" not in data


def test_verify_endpoint_system_chain(client: TestClient, db_session: Session) -> None:
    """The system chain (no document_id) is verifiable via the API."""
    for note in ("sys-1", "sys-2"):
        append(db_session, None, note)

    response = client.get(
        VERIFY_URL,
        headers={ROLE_HEADER: UserRole.AUDITOR.value},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["is_valid"] is True
    assert data["document_id"] is None


def test_verify_endpoint_unknown_document_returns_error(
    client: TestClient,
) -> None:
    """A document_id with no chain entries surfaces as an error, not a false pass."""
    response = client.get(
        VERIFY_URL,
        params={"document_id": str(uuid4())},
        headers={ROLE_HEADER: UserRole.AUDITOR.value},
    )
    # An empty chain raises ValueError in the service; the endpoint maps it to 422.
    assert response.status_code == 422


def test_verify_endpoint_forked_chain_returns_409(
    client: TestClient,
    registered_document: Document,
) -> None:
    """A broken or forked chain surfaces as 409, not a silent pass or 500.

    The database trigger prevents a real forked chain from being written, so
    the exception is injected via a mock. The route must catch
    ``AuditChainError`` and map it to 409; this test asserts that mapping
    without relying on a state the trigger forbids.
    """
    from unittest.mock import patch

    from app.db.repositories.audit import AuditChainError

    with patch(
        "app.api.routes.audit.verify_chain_range",
        side_effect=AuditChainError("Simulated forked chain for test"),
    ):
        response = client.get(
            VERIFY_URL,
            params={"document_id": str(registered_document.id)},
            headers={ROLE_HEADER: UserRole.AUDITOR.value},
        )

    assert response.status_code == 409
    assert "forked" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# GET /audit/entries, PRD.md FR-15
# ---------------------------------------------------------------------------


def test_entries_endpoint_rejects_a_caller_with_no_role(
    client: TestClient, registered_document: Document
) -> None:
    response = client.get(
        ENTRIES_URL, params={"document_id": str(registered_document.id)}
    )
    assert response.status_code == 401


@pytest.mark.parametrize(
    "role",
    [UserRole.AUDITOR, UserRole.SECURITY_ADMIN, UserRole.SECURITY_ANALYST],
)
def test_entries_endpoint_admits_permitted_roles(
    client: TestClient, registered_document: Document, role: UserRole
) -> None:
    response = client.get(
        ENTRIES_URL,
        params={"document_id": str(registered_document.id)},
        headers={ROLE_HEADER: role.value},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["document_id"] == str(registered_document.id)
    assert payload["count"] == 0
    assert payload["entries"] == []


@pytest.mark.parametrize(
    "role",
    [
        UserRole.DATA_OWNER,
        UserRole.COMPLIANCE_OFFICER,
        UserRole.CISO,
        UserRole.ENGINEER,
    ],
)
def test_entries_endpoint_refuses_excluded_roles(
    client: TestClient, registered_document: Document, role: UserRole
) -> None:
    response = client.get(
        ENTRIES_URL,
        params={"document_id": str(registered_document.id)},
        headers={ROLE_HEADER: role.value},
    )
    assert response.status_code == 403


def test_entries_endpoint_requires_a_document_id(client: TestClient) -> None:
    response = client.get(ENTRIES_URL, headers={ROLE_HEADER: UserRole.AUDITOR.value})
    assert response.status_code == 422


def test_entries_endpoint_unknown_document_is_404(client: TestClient) -> None:
    response = client.get(
        ENTRIES_URL,
        params={"document_id": str(uuid4())},
        headers={ROLE_HEADER: UserRole.AUDITOR.value},
    )
    assert response.status_code == 404


def test_entries_endpoint_returns_the_chain_in_link_order(
    client: TestClient, registered_document: Document, db_session: Session
) -> None:
    first = append(db_session, registered_document.id, "one")
    second = append(db_session, registered_document.id, "two")
    third = append(db_session, registered_document.id, "three")

    response = client.get(
        ENTRIES_URL,
        params={"document_id": str(registered_document.id)},
        headers={ROLE_HEADER: UserRole.AUDITOR.value},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["count"] == 3
    notes = [entry["payload"]["note"] for entry in payload["entries"]]
    assert notes == ["one", "two", "three"]
    assert [entry["index"] for entry in payload["entries"]] == [0, 1, 2]
    assert payload["entries"][0]["id"] == str(first.id)
    assert payload["entries"][0]["prev_hash"] is None
    assert payload["entries"][1]["prev_hash"] == first.payload_hash
    assert payload["entries"][2]["prev_hash"] == second.payload_hash
    assert payload["entries"][2]["payload_hash"] == third.payload_hash
    assert "frontier" not in payload["entries"][0]
    assert "is_valid" not in payload


def test_entries_endpoint_includes_the_actor(
    client: TestClient,
    registered_document: Document,
    db_session: Session,
    seeded_users: dict,
) -> None:
    actor = seeded_users[UserRole.SECURITY_ANALYST]
    audit_repo.append_entry(
        db_session,
        event_type=EVENT,
        document_id=registered_document.id,
        actor_id=actor.id,
        payload={"note": "acted"},
    )
    response = client.get(
        ENTRIES_URL,
        params={"document_id": str(registered_document.id)},
        headers={ROLE_HEADER: UserRole.AUDITOR.value},
    )
    assert response.status_code == 200, response.text
    entry = response.json()["entries"][0]
    assert entry["actor_id"] == str(actor.id)
    assert entry["event_type"] == EVENT


def test_reading_entries_writes_nothing(
    client: TestClient, registered_document: Document, db_session: Session
) -> None:
    append(db_session, registered_document.id, "only")
    before = len(audit_repo.load_chain(db_session, registered_document.id))
    response = client.get(
        ENTRIES_URL,
        params={"document_id": str(registered_document.id)},
        headers={ROLE_HEADER: UserRole.AUDITOR.value},
    )
    assert response.status_code == 200, response.text
    assert len(audit_repo.load_chain(db_session, registered_document.id)) == before


def test_entries_endpoint_forked_chain_returns_409(
    client: TestClient, registered_document: Document
) -> None:
    from unittest.mock import patch

    from app.db.repositories.audit import AuditChainError

    with patch(
        "app.api.routes.audit.load_chain",
        side_effect=AuditChainError("Simulated forked chain for test"),
    ):
        response = client.get(
            ENTRIES_URL,
            params={"document_id": str(registered_document.id)},
            headers={ROLE_HEADER: UserRole.AUDITOR.value},
        )
    assert response.status_code == 409
    assert "forked" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# build_inclusion_proof / build_consistency_proof: service over the real chain
#
# The proofs are the point where an auditor stops needing the whole log. These
# tests build a proof from the stored chain, then verify it with the pure
# functions given only the proof and roots — never the other entries.
# ---------------------------------------------------------------------------


def test_build_inclusion_proof_verifies_against_recomputed_root(
    db_session: Session, registered_document: Document
) -> None:
    """A proof from the chain verifies for every entry against the real root."""
    notes = ["a", "b", "c", "d", "e", "f", "g"]
    for note in notes:
        append(db_session, registered_document.id, note)

    for index in range(len(notes)):
        result = build_inclusion_proof(db_session, registered_document.id, index)
        assert result.proof.leaf_index == index
        assert result.proof.tree_size == len(notes)
        assert verify_inclusion(result.proof, result.leaf_hash, result.root)
        # The returned root is the chain's true root, not a stored claim.
        assert result.root == audit_repo.current_root(
            db_session, registered_document.id
        )


def test_inclusion_proof_leaf_hash_matches_the_stored_payload(
    db_session: Session, registered_document: Document
) -> None:
    """leaf_hash is recomputable from the returned payload, closing the loop."""
    for note in ("one", "two", "three"):
        append(db_session, registered_document.id, note)

    result = build_inclusion_proof(db_session, registered_document.id, 1)
    assert result.payload == {"note": "two"}
    assert result.leaf_hash == hash_leaf(canonicalize(result.payload))


def test_inclusion_proof_against_an_older_tree_size(
    db_session: Session, registered_document: Document
) -> None:
    """A proof can target a past size, i.e. an already-anchored root."""
    for note in ("a", "b", "c", "d", "e"):
        append(db_session, registered_document.id, note)

    result = build_inclusion_proof(db_session, registered_document.id, 1, tree_size=3)
    assert result.proof.tree_size == 3
    # Root of the first three entries only, independently recomputed.
    chain = audit_repo.load_chain(db_session, registered_document.id)
    prefix_root = build([canonicalize(e.payload) for e in chain[:3]]).root
    assert result.root == prefix_root
    assert verify_inclusion(result.proof, result.leaf_hash, result.root)


def test_inclusion_proof_out_of_range_raises(
    db_session: Session, registered_document: Document
) -> None:
    """Indices and tree sizes outside the chain are caller errors."""
    for note in ("a", "b"):
        append(db_session, registered_document.id, note)

    with pytest.raises(ValueError):
        build_inclusion_proof(db_session, registered_document.id, 5)
    with pytest.raises(ValueError):
        build_inclusion_proof(db_session, registered_document.id, 0, tree_size=9)


def test_inclusion_proof_empty_chain_raises(
    db_session: Session, registered_document: Document
) -> None:
    """An empty chain has nothing to prove."""
    with pytest.raises(ValueError):
        build_inclusion_proof(db_session, registered_document.id, 0)


def test_build_consistency_proof_verifies_every_prefix(
    db_session: Session, registered_document: Document
) -> None:
    """Every earlier prefix proves consistent with the full chain."""
    notes = ["a", "b", "c", "d", "e", "f"]
    for note in notes:
        append(db_session, registered_document.id, note)

    for old_size in range(len(notes) + 1):
        result = build_consistency_proof(db_session, registered_document.id, old_size)
        assert verify_consistency(result.proof, result.old_root, result.new_root)


def test_consistency_proof_detects_a_rewritten_prefix(
    db_session: Session, registered_document: Document, monkeypatch: pytest.MonkeyPatch
) -> None:
    """If the anchored old root disagrees, consistency verification fails.

    The DB trigger forbids editing a stored row, so the "rewrite" is a genuine
    earlier root, captured before more entries were appended, checked against a
    later chain whose head is rebuilt differently through the load_chain seam.
    """
    for note in ("a", "b", "c"):
        append(db_session, registered_document.id, note)
    genuine_old_root = audit_repo.current_root(db_session, registered_document.id)

    for note in ("d", "e"):
        append(db_session, registered_document.id, note)

    real_chain = audit_repo.load_chain(db_session, registered_document.id)
    rewritten = [
        SimpleNamespace(
            payload=({"note": "a-ALTERED"} if i == 0 else dict(entry.payload)),
            merkle_root_at_time=entry.merkle_root_at_time,
        )
        for i, entry in enumerate(real_chain)
    ]
    monkeypatch.setattr(audit_service, "load_chain", lambda session, doc_id: rewritten)

    result = build_consistency_proof(db_session, registered_document.id, 3)
    # The proof is built over the rewritten chain, so its old_root no longer
    # matches the genuine earlier root an auditor anchored.
    assert result.old_root != genuine_old_root
    assert not verify_consistency(result.proof, genuine_old_root, result.new_root)


def test_consistency_proof_out_of_range_raises(
    db_session: Session, registered_document: Document
) -> None:
    """Sizes must satisfy 0 <= old_size <= new_size <= chain length."""
    for note in ("a", "b", "c"):
        append(db_session, registered_document.id, note)

    with pytest.raises(ValueError):
        build_consistency_proof(db_session, registered_document.id, 5)
    with pytest.raises(ValueError):
        build_consistency_proof(db_session, registered_document.id, 2, new_size=9)


# ---------------------------------------------------------------------------
# Proof API endpoints
# ---------------------------------------------------------------------------


def test_inclusion_proof_endpoint_returns_a_verifiable_proof(
    client: TestClient, registered_document: Document, db_session: Session
) -> None:
    """The endpoint hands back a proof a client verifies with the pure code."""
    for note in ("a", "b", "c", "d"):
        append(db_session, registered_document.id, note)

    response = client.get(
        INCLUSION_URL,
        params={"document_id": str(registered_document.id), "leaf_index": 2},
        headers={ROLE_HEADER: UserRole.AUDITOR.value},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["leaf_index"] == 2
    assert data["tree_size"] == 4
    assert data["payload"] == {"note": "c"}
    # Reconstruct the pure proof from the response and verify independently.
    from app.audit.merkle import InclusionProof

    proof = InclusionProof(
        leaf_index=data["leaf_index"],
        tree_size=data["tree_size"],
        audit_path=tuple(data["audit_path"]),
    )
    assert verify_inclusion(proof, data["leaf_hash"], data["root"])


def test_consistency_proof_endpoint_returns_a_verifiable_proof(
    client: TestClient, registered_document: Document, db_session: Session
) -> None:
    """The endpoint hands back a consistency proof checkable client-side."""
    for note in ("a", "b", "c", "d", "e"):
        append(db_session, registered_document.id, note)

    response = client.get(
        CONSISTENCY_URL,
        params={"document_id": str(registered_document.id), "old_size": 2},
        headers={ROLE_HEADER: UserRole.AUDITOR.value},
    )
    assert response.status_code == 200, response.text
    data = response.json()
    assert data["old_size"] == 2
    assert data["new_size"] == 5
    from app.audit.merkle import ConsistencyProof

    proof = ConsistencyProof(
        old_size=data["old_size"],
        new_size=data["new_size"],
        nodes=tuple(data["nodes"]),
    )
    assert verify_consistency(proof, data["old_root"], data["new_root"])


@pytest.mark.parametrize("url", [INCLUSION_URL, CONSISTENCY_URL])
def test_proof_endpoints_require_a_permitted_role(
    client: TestClient, registered_document: Document, url: str
) -> None:
    """Missing header is 401; an excluded role is 403."""
    param = "leaf_index" if url == INCLUSION_URL else "old_size"
    base = {"document_id": str(registered_document.id), param: 0}

    assert client.get(url, params=base).status_code == 401
    assert (
        client.get(
            url, params=base, headers={ROLE_HEADER: UserRole.ENGINEER.value}
        ).status_code
        == 403
    )


@pytest.mark.parametrize("url", [INCLUSION_URL, CONSISTENCY_URL])
def test_proof_endpoints_empty_chain_is_422(
    client: TestClient, registered_document: Document, url: str
) -> None:
    """A chain with no entries yields 422, not a false proof."""
    param = "leaf_index" if url == INCLUSION_URL else "old_size"
    response = client.get(
        url,
        params={"document_id": str(registered_document.id), param: 0},
        headers={ROLE_HEADER: UserRole.AUDITOR.value},
    )
    assert response.status_code == 422
