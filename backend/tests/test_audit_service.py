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
from app.audit.service import verify_chain_range
from app.db.enums import AuditEventType, UserRole
from app.db.models import Document
from app.db.repositories import audit as audit_repo

EVENT = AuditEventType.CLASSIFICATION_COMPLETED.value

VERIFY_URL = "/api/v1/audit/verify"
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
