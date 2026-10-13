"""PQ-signed audit checkpoint anchoring, ``SPEC.md`` 3.8, ``PRD.md`` FR-7.

Four layers, tested from the pure core outward:

1. :func:`checkpoint_signing_input` — the canonical bytes are deterministic,
   injective across every field, and reject malformed input. No DB, no liboqs.
2. sign / verify round-trip with ML-DSA-87. Gated on liboqs being installed;
   skipped (never silently passed) when it is not.
3. The service: :func:`create_checkpoint` recomputes a root, signs it, and
   persists a Signed Tree Head; :func:`verify_checkpoint` re-derives the signed
   bytes and both verifies the signature and recomputes the root. The rewrite
   case is the point of the whole feature: a valid signature over a root that no
   longer matches is the tamper signal.
4. The API: role gating (issuing is stricter than reading), fail-closed 503 when
   liboqs is unavailable, and public-key pinning.

Never add UPDATE or DELETE against the checkpoint tables; they are append-only
at the database level, and :mod:`tests.test_db_append_only` proves it.
"""

from datetime import datetime, timezone
from unittest.mock import patch
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.audit import service as audit_service
from app.audit.checkpoint import (
    CHECKPOINT_DOMAIN,
    CHECKPOINT_SIGNATURE_ALGORITHM,
    checkpoint_signing_input,
    generate_signing_keypair,
    sign_checkpoint,
    verify_checkpoint_signature,
)
from app.audit.service import (
    create_checkpoint,
    get_active_signing_key_info,
    verify_checkpoint,
)
from app.crypto.oqs_support import oqs_available
from app.db.enums import AuditEventType, UserRole
from app.db.models import Document
from app.db.repositories import audit as audit_repo
from app.db.repositories import checkpoint as checkpoint_repo

EVENT = AuditEventType.CLASSIFICATION_COMPLETED.value
ROLE_HEADER = "X-Q-AEGIS-Actor-Role"

CHECKPOINT_URL = "/api/v1/audit/checkpoint"
CHECKPOINTS_URL = "/api/v1/audit/checkpoints"
SIGNING_KEY_URL = "/api/v1/audit/signing-key"


def _verify_url(checkpoint_id: object) -> str:
    return f"/api/v1/audit/checkpoint/{checkpoint_id}/verify"


def _append(session: Session, document_id: object, note: str) -> object:
    return audit_repo.append_entry(
        session, event_type=EVENT, document_id=document_id, payload={"note": note}
    )


def _requires_oqs() -> None:
    if not oqs_available():
        pytest.skip("liboqs-python is not installed")


ROOT_A = "a" * 64
ROOT_B = "b" * 64
WHEN = datetime(2026, 9, 23, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# 1. checkpoint_signing_input: pure, deterministic, injective, validated
# ---------------------------------------------------------------------------


def test_signing_input_is_deterministic() -> None:
    """Identical fields produce byte-identical output, every time."""
    doc = uuid4()
    first = checkpoint_signing_input(
        document_id=doc, tree_size=7, signed_at=WHEN, merkle_root=ROOT_A
    )
    second = checkpoint_signing_input(
        document_id=doc, tree_size=7, signed_at=WHEN, merkle_root=ROOT_A
    )
    assert first == second


def test_signing_input_starts_with_the_domain_tag() -> None:
    """Domain separation: the bytes are prefixed so they can never be replayed."""
    payload = checkpoint_signing_input(
        document_id=None, tree_size=1, signed_at=WHEN, merkle_root=ROOT_A
    )
    assert payload.startswith(CHECKPOINT_DOMAIN)


def test_signing_input_distinguishes_system_chain_from_a_document() -> None:
    """None (system chain) and a real document_id must never collide."""
    system = checkpoint_signing_input(
        document_id=None, tree_size=1, signed_at=WHEN, merkle_root=ROOT_A
    )
    doc = checkpoint_signing_input(
        document_id=uuid4(), tree_size=1, signed_at=WHEN, merkle_root=ROOT_A
    )
    assert system != doc


def test_signing_input_is_injective_across_every_field() -> None:
    """Changing any single field changes the bytes (no field is dropped)."""
    doc = uuid4()
    other_doc = uuid4()
    base = checkpoint_signing_input(
        document_id=doc, tree_size=7, signed_at=WHEN, merkle_root=ROOT_A
    )
    variants = [
        checkpoint_signing_input(
            document_id=other_doc, tree_size=7, signed_at=WHEN, merkle_root=ROOT_A
        ),
        checkpoint_signing_input(
            document_id=doc, tree_size=8, signed_at=WHEN, merkle_root=ROOT_A
        ),
        checkpoint_signing_input(
            document_id=doc,
            tree_size=7,
            signed_at=datetime(2026, 9, 23, 12, 0, 1, tzinfo=timezone.utc),
            merkle_root=ROOT_A,
        ),
        checkpoint_signing_input(
            document_id=doc, tree_size=7, signed_at=WHEN, merkle_root=ROOT_B
        ),
    ]
    assert all(variant != base for variant in variants)
    # And all distinct from each other.
    assert len(set(variants)) == len(variants)


def test_signing_input_naive_datetime_is_treated_as_utc() -> None:
    """A naive timestamp equals the same instant expressed in UTC, not a guess."""
    naive = datetime(2026, 9, 23, 12, 0, 0)
    aware = datetime(2026, 9, 23, 12, 0, 0, tzinfo=timezone.utc)
    assert checkpoint_signing_input(
        document_id=None, tree_size=1, signed_at=naive, merkle_root=ROOT_A
    ) == checkpoint_signing_input(
        document_id=None, tree_size=1, signed_at=aware, merkle_root=ROOT_A
    )


def test_signing_input_micros_survive_a_non_utc_zone() -> None:
    """Two spellings of one instant in different zones sign identically."""
    from datetime import timedelta

    plus_two = timezone(timedelta(hours=2))
    in_utc = datetime(2026, 9, 23, 12, 0, 0, 500_000, tzinfo=timezone.utc)
    in_plus_two = datetime(2026, 9, 23, 14, 0, 0, 500_000, tzinfo=plus_two)
    assert checkpoint_signing_input(
        document_id=None, tree_size=3, signed_at=in_utc, merkle_root=ROOT_A
    ) == checkpoint_signing_input(
        document_id=None, tree_size=3, signed_at=in_plus_two, merkle_root=ROOT_A
    )


def test_signing_input_rejects_negative_tree_size() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        checkpoint_signing_input(
            document_id=None, tree_size=-1, signed_at=WHEN, merkle_root=ROOT_A
        )


def test_signing_input_rejects_a_wrong_length_root() -> None:
    with pytest.raises(ValueError, match="hex chars"):
        checkpoint_signing_input(
            document_id=None, tree_size=1, signed_at=WHEN, merkle_root="a" * 63
        )


def test_signing_input_rejects_non_hex_root() -> None:
    with pytest.raises(ValueError, match="hex"):
        checkpoint_signing_input(
            document_id=None, tree_size=1, signed_at=WHEN, merkle_root="z" * 64
        )


# ---------------------------------------------------------------------------
# 2. ML-DSA-87 sign / verify round-trip (gated on liboqs)
# ---------------------------------------------------------------------------


def test_sign_then_verify_round_trips() -> None:
    """A signature over the canonical bytes verifies under the public key."""
    _requires_oqs()
    public_key, secret_key = generate_signing_keypair()
    signing_input = checkpoint_signing_input(
        document_id=uuid4(), tree_size=4, signed_at=WHEN, merkle_root=ROOT_A
    )
    signature = sign_checkpoint(signing_input, secret_key)
    assert verify_checkpoint_signature(signing_input, signature, public_key)


def test_verify_rejects_a_tampered_input() -> None:
    """Flipping the signed bytes makes verification fail."""
    _requires_oqs()
    public_key, secret_key = generate_signing_keypair()
    signing_input = checkpoint_signing_input(
        document_id=None, tree_size=4, signed_at=WHEN, merkle_root=ROOT_A
    )
    signature = sign_checkpoint(signing_input, secret_key)
    forged = checkpoint_signing_input(
        document_id=None, tree_size=5, signed_at=WHEN, merkle_root=ROOT_A
    )
    assert not verify_checkpoint_signature(forged, signature, public_key)


def test_verify_rejects_a_foreign_key() -> None:
    """A signature does not verify under a different keypair's public key."""
    _requires_oqs()
    _, secret_key = generate_signing_keypair()
    other_public, _ = generate_signing_keypair()
    signing_input = checkpoint_signing_input(
        document_id=None, tree_size=4, signed_at=WHEN, merkle_root=ROOT_A
    )
    signature = sign_checkpoint(signing_input, secret_key)
    assert not verify_checkpoint_signature(signing_input, signature, other_public)


# ---------------------------------------------------------------------------
# 3. Service: create_checkpoint / verify_checkpoint over a real chain
# ---------------------------------------------------------------------------


def test_create_checkpoint_anchors_and_bootstraps_a_key(
    db_session: Session, registered_document: Document
) -> None:
    """The first checkpoint issues the signing key and commits to the real root."""
    _requires_oqs()
    for note in ("a", "b", "c"):
        _append(db_session, registered_document.id, note)

    result = create_checkpoint(db_session, registered_document.id)

    assert result.tree_size == 3
    assert result.algorithm == CHECKPOINT_SIGNATURE_ALGORITHM
    assert result.merkle_root == audit_repo.current_root(
        db_session, registered_document.id
    )
    # The row is persisted and its signing key exists.
    stored = checkpoint_repo.get_checkpoint(db_session, result.checkpoint_id)
    assert stored is not None
    assert (
        checkpoint_repo.get_signing_key(db_session, result.signing_key_id) is not None
    )


def test_created_checkpoint_verifies_clean(
    db_session: Session, registered_document: Document
) -> None:
    """A freshly issued checkpoint verifies: signature valid and root matches."""
    _requires_oqs()
    for note in ("a", "b", "c", "d"):
        _append(db_session, registered_document.id, note)

    created = create_checkpoint(db_session, registered_document.id)
    verdict = verify_checkpoint(db_session, created.checkpoint_id)

    assert verdict.is_valid
    assert verdict.signature_valid
    assert verdict.root_matches
    assert verdict.recomputed_root == created.merkle_root


def test_second_checkpoint_reuses_the_active_key(
    db_session: Session, registered_document: Document
) -> None:
    """A single pinned key covers the whole series; issuing does not rotate it."""
    _requires_oqs()
    _append(db_session, registered_document.id, "a")
    first = create_checkpoint(db_session, registered_document.id)
    _append(db_session, registered_document.id, "b")
    second = create_checkpoint(db_session, registered_document.id)

    assert first.signing_key_id == second.signing_key_id
    assert first.public_key == second.public_key
    assert second.tree_size == 2


def test_checkpoint_over_an_older_prefix(
    db_session: Session, registered_document: Document
) -> None:
    """A checkpoint can anchor a smaller, already-published prefix."""
    _requires_oqs()
    for note in ("a", "b", "c", "d", "e"):
        _append(db_session, registered_document.id, note)

    created = create_checkpoint(db_session, registered_document.id, tree_size=3)
    assert created.tree_size == 3

    chain = audit_repo.load_chain(db_session, registered_document.id)
    from app.audit.merkle import build, canonicalize

    prefix_root = build([canonicalize(e.payload) for e in chain[:3]]).root
    assert created.merkle_root == prefix_root
    assert verify_checkpoint(db_session, created.checkpoint_id).is_valid


def test_checkpoint_on_the_system_chain(db_session: Session) -> None:
    """The document-less system chain anchors just like a per-document one."""
    _requires_oqs()
    for note in ("sys-1", "sys-2"):
        _append(db_session, None, note)

    created = create_checkpoint(db_session, None)
    assert created.document_id is None
    assert verify_checkpoint(db_session, created.checkpoint_id).is_valid


def test_verify_detects_a_rewritten_chain(
    db_session: Session,
    registered_document: Document,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The whole point: a valid signature over a root that no longer matches.

    The DB trigger forbids editing a stored row, so the rewrite is injected
    through the ``load_chain`` seam the service reads on verification. The
    signature still verifies (its bytes are rebuilt from the checkpoint's own
    immutable fields), but the recomputed root diverges — which is exactly the
    tamper signal external anchoring exists to raise.
    """
    _requires_oqs()
    for note in ("a", "b", "c"):
        _append(db_session, registered_document.id, note)
    created = create_checkpoint(db_session, registered_document.id)

    from types import SimpleNamespace

    real_chain = audit_repo.load_chain(db_session, registered_document.id)
    rewritten = [
        SimpleNamespace(
            payload=({"note": "a-ALTERED"} if i == 0 else dict(entry.payload)),
            merkle_root_at_time=entry.merkle_root_at_time,
        )
        for i, entry in enumerate(real_chain)
    ]
    monkeypatch.setattr(audit_service, "load_chain", lambda session, doc_id: rewritten)

    verdict = verify_checkpoint(db_session, created.checkpoint_id)
    assert verdict.signature_valid
    assert not verdict.root_matches
    assert not verdict.is_valid
    assert verdict.recomputed_root != verdict.stored_root


def test_verify_flags_a_chain_now_shorter_than_the_prefix(
    db_session: Session,
    registered_document: Document,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If the chain is truncated below tree_size there is no prefix to match."""
    _requires_oqs()
    for note in ("a", "b", "c"):
        _append(db_session, registered_document.id, note)
    created = create_checkpoint(db_session, registered_document.id)

    from types import SimpleNamespace

    real_chain = audit_repo.load_chain(db_session, registered_document.id)
    truncated = [
        SimpleNamespace(
            payload=dict(entry.payload),
            merkle_root_at_time=entry.merkle_root_at_time,
        )
        for entry in real_chain[:1]
    ]
    monkeypatch.setattr(audit_service, "load_chain", lambda session, doc_id: truncated)

    verdict = verify_checkpoint(db_session, created.checkpoint_id)
    assert verdict.recomputed_root == ""
    assert not verdict.is_valid


def test_create_checkpoint_empty_chain_raises(
    db_session: Session, registered_document: Document
) -> None:
    """There is nothing to anchor on an empty chain."""
    _requires_oqs()
    with pytest.raises(ValueError, match="no entries"):
        create_checkpoint(db_session, registered_document.id)


def test_create_checkpoint_out_of_range_tree_size_raises(
    db_session: Session, registered_document: Document
) -> None:
    """tree_size beyond the chain length is a caller error."""
    _requires_oqs()
    _append(db_session, registered_document.id, "a")
    with pytest.raises(ValueError, match="between 1 and"):
        create_checkpoint(db_session, registered_document.id, tree_size=9)


def test_create_checkpoint_fails_closed_without_liboqs(
    db_session: Session, registered_document: Document
) -> None:
    """No liboqs means an explicit refusal, never a silently unsigned commitment.

    Patched so the guarantee holds regardless of whether the host has liboqs.
    """
    from app.crypto.exceptions import LiboqsUnavailableError

    _append(db_session, registered_document.id, "a")
    with patch("app.crypto.oqs_support.oqs_available", return_value=False):
        with pytest.raises(LiboqsUnavailableError):
            create_checkpoint(db_session, registered_document.id)
    # And nothing was persisted: no key, no checkpoint.
    assert get_active_signing_key_info(db_session) is None
    assert checkpoint_repo.list_checkpoints(db_session, registered_document.id) == []


def test_verify_unknown_checkpoint_raises(db_session: Session) -> None:
    """Verifying a checkpoint id that does not exist is a caller error."""
    with pytest.raises(ValueError, match="not found"):
        verify_checkpoint(db_session, uuid4())


def test_active_signing_key_info_is_none_before_any_checkpoint(
    db_session: Session,
) -> None:
    """The key is created lazily; none exists until the first checkpoint."""
    assert get_active_signing_key_info(db_session) is None


# ---------------------------------------------------------------------------
# 4a. POST /audit/checkpoint — issuing is stricter than reading
# ---------------------------------------------------------------------------


def test_issue_checkpoint_requires_a_role(
    client: TestClient, registered_document: Document
) -> None:
    """A missing role header is 401 before any database access."""
    response = client.post(
        CHECKPOINT_URL, json={"document_id": str(registered_document.id)}
    )
    assert response.status_code == 401


def test_issue_checkpoint_refuses_an_analyst(
    client: TestClient, registered_document: Document
) -> None:
    """A security analyst may read the trail but not mint tamper-evidence."""
    response = client.post(
        CHECKPOINT_URL,
        json={"document_id": str(registered_document.id)},
        headers={ROLE_HEADER: UserRole.SECURITY_ANALYST.value},
    )
    assert response.status_code == 403


@pytest.mark.parametrize(
    "role",
    [
        UserRole.DATA_OWNER,
        UserRole.COMPLIANCE_OFFICER,
        UserRole.CISO,
        UserRole.ENGINEER,
    ],
)
def test_issue_checkpoint_refuses_excluded_roles(
    client: TestClient, registered_document: Document, role: UserRole
) -> None:
    response = client.post(
        CHECKPOINT_URL,
        json={"document_id": str(registered_document.id)},
        headers={ROLE_HEADER: role.value},
    )
    assert response.status_code == 403


def test_issue_checkpoint_empty_chain_is_422(
    client: TestClient, registered_document: Document
) -> None:
    """An empty chain is refused before any signing occurs."""
    response = client.post(
        CHECKPOINT_URL,
        json={"document_id": str(registered_document.id)},
        headers={ROLE_HEADER: UserRole.AUDITOR.value},
    )
    assert response.status_code == 422


def test_issue_checkpoint_fails_closed_without_liboqs(
    client: TestClient, registered_document: Document, db_session: Session
) -> None:
    """Without liboqs the endpoint returns 503, never a silently unsigned row."""
    _append(db_session, registered_document.id, "a")
    with patch("app.crypto.oqs_support.oqs_available", return_value=False):
        response = client.post(
            CHECKPOINT_URL,
            json={"document_id": str(registered_document.id)},
            headers={ROLE_HEADER: UserRole.AUDITOR.value},
        )
    assert response.status_code == 503


@pytest.mark.parametrize("role", [UserRole.AUDITOR, UserRole.SECURITY_ADMIN])
def test_issue_checkpoint_admits_creator_roles(
    client: TestClient,
    registered_document: Document,
    db_session: Session,
    role: UserRole,
) -> None:
    """Auditor and security admin can anchor a chain."""
    _requires_oqs()
    _append(db_session, registered_document.id, "a")
    _append(db_session, registered_document.id, "b")

    response = client.post(
        CHECKPOINT_URL,
        json={"document_id": str(registered_document.id)},
        headers={ROLE_HEADER: role.value},
    )
    assert response.status_code == 201, response.text
    data = response.json()
    assert data["tree_size"] == 2
    assert data["algorithm"] == CHECKPOINT_SIGNATURE_ALGORITHM
    assert data["document_id"] == str(registered_document.id)


# ---------------------------------------------------------------------------
# 4b. Read endpoints: verify, list, signing-key
# ---------------------------------------------------------------------------


def test_verify_endpoint_unknown_checkpoint_is_404(client: TestClient) -> None:
    response = client.get(
        _verify_url(uuid4()), headers={ROLE_HEADER: UserRole.AUDITOR.value}
    )
    assert response.status_code == 404


def test_verify_endpoint_requires_a_role(client: TestClient) -> None:
    assert client.get(_verify_url(uuid4())).status_code == 401


def test_signing_key_endpoint_is_404_before_any_checkpoint(
    client: TestClient,
) -> None:
    """No key exists until the first checkpoint is issued."""
    response = client.get(
        SIGNING_KEY_URL, headers={ROLE_HEADER: UserRole.AUDITOR.value}
    )
    assert response.status_code == 404


def test_signing_key_endpoint_requires_a_role(client: TestClient) -> None:
    assert client.get(SIGNING_KEY_URL).status_code == 401


def test_signing_key_endpoint_refuses_excluded_role(client: TestClient) -> None:
    response = client.get(
        SIGNING_KEY_URL, headers={ROLE_HEADER: UserRole.ENGINEER.value}
    )
    assert response.status_code == 403


def test_checkpoints_list_is_empty_and_readable(
    client: TestClient, registered_document: Document
) -> None:
    """An analyst may list; with nothing issued the list is empty, not an error."""
    response = client.get(
        CHECKPOINTS_URL,
        params={"document_id": str(registered_document.id)},
        headers={ROLE_HEADER: UserRole.SECURITY_ANALYST.value},
    )
    assert response.status_code == 200
    assert response.json() == []


def test_checkpoints_list_requires_a_role(client: TestClient) -> None:
    assert client.get(CHECKPOINTS_URL).status_code == 401


def test_checkpoints_list_refuses_excluded_role(client: TestClient) -> None:
    response = client.get(
        CHECKPOINTS_URL, headers={ROLE_HEADER: UserRole.DATA_OWNER.value}
    )
    assert response.status_code == 403


# ---------------------------------------------------------------------------
# 4c. Full API round-trip: create -> verify -> pin -> list
# ---------------------------------------------------------------------------


def test_api_round_trip_create_verify_pin_list(
    client: TestClient, registered_document: Document, db_session: Session
) -> None:
    """Issue over the API, then verify, pin the key, and list — all consistent."""
    _requires_oqs()
    for note in ("a", "b", "c"):
        _append(db_session, registered_document.id, note)

    created = client.post(
        CHECKPOINT_URL,
        json={"document_id": str(registered_document.id)},
        headers={ROLE_HEADER: UserRole.AUDITOR.value},
    )
    assert created.status_code == 201, created.text
    checkpoint = created.json()

    verified = client.get(
        _verify_url(checkpoint["checkpoint_id"]),
        headers={ROLE_HEADER: UserRole.AUDITOR.value},
    )
    assert verified.status_code == 200, verified.text
    verdict = verified.json()
    assert verdict["is_valid"] is True
    assert verdict["signature_valid"] is True
    assert verdict["root_matches"] is True

    # Public-key pinning: the signing-key endpoint returns the same key the
    # checkpoint verifies under, so an auditor can pin it and re-check offline.
    pinned = client.get(SIGNING_KEY_URL, headers={ROLE_HEADER: UserRole.AUDITOR.value})
    assert pinned.status_code == 200, pinned.text
    key = pinned.json()
    assert key["public_key"] == checkpoint["public_key"]
    assert key["signing_key_id"] == checkpoint["signing_key_id"]

    # The offline check an auditor would run, using only exported values.
    signing_input = checkpoint_signing_input(
        document_id=registered_document.id,
        tree_size=checkpoint["tree_size"],
        signed_at=datetime.fromisoformat(checkpoint["signed_at"]),
        merkle_root=checkpoint["merkle_root"],
    )
    assert verify_checkpoint_signature(
        signing_input,
        bytes.fromhex(checkpoint["signature"]),
        bytes.fromhex(key["public_key"]),
    )

    listed = client.get(
        CHECKPOINTS_URL,
        params={"document_id": str(registered_document.id)},
        headers={ROLE_HEADER: UserRole.AUDITOR.value},
    )
    assert listed.status_code == 200
    rows = listed.json()
    assert len(rows) == 1
    assert rows[0]["checkpoint_id"] == checkpoint["checkpoint_id"]
    assert rows[0]["public_key"] == checkpoint["public_key"]
