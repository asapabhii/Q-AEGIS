"""Crypto-shredding tests, ``SPEC.md`` 3.9 / FR-8."""

from __future__ import annotations

import base64
import os

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.crypto.engine import encrypt_document_bytes
from app.crypto.exceptions import CryptoDecryptError
from app.crypto.key_management import unwrap_dek
from app.crypto.shred import SHRED_MARKER, is_shredded, shred_wrapped_dek
from app.db.enums import AuditEventType, CryptoProfileType, UserRole
from app.db.models import AuditLog
from app.db.repositories import ciphertexts as ciphertext_repo
from tests.factories import make_crypto_profile, make_risk_score, make_trust_score


@pytest.fixture
def master_key(monkeypatch: pytest.MonkeyPatch) -> bytes:
    raw = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")
    monkeypatch.setenv("CRYPTO_MASTER_KEY", raw)
    return base64.urlsafe_b64decode(raw + "=" * (-len(raw) % 4))


def test_shred_wrapped_dek_is_irreversible(master_key: bytes) -> None:
    payload = b"\x01" + os.urandom(32)
    from app.crypto.key_management import wrap_dek

    wrapped = wrap_dek(payload, master_key=master_key)
    shredded = shred_wrapped_dek(wrapped)
    assert is_shredded(shredded)
    assert shredded.startswith(SHRED_MARKER)
    assert len(shredded) == len(wrapped)
    with pytest.raises(CryptoDecryptError):
        unwrap_dek(shredded, master_key=master_key)


def _seed_ciphertext(db_session: Session, registered_document, master_key: bytes):
    risk = make_risk_score(db_session, registered_document)
    trust = make_trust_score(db_session, registered_document, risk)
    profile = make_crypto_profile(db_session, registered_document, trust)
    result = encrypt_document_bytes(
        b"erase-me",
        CryptoProfileType.AES256,
        master_key=master_key,
    )
    row = ciphertext_repo.append_ciphertext(
        db_session,
        document_id=registered_document.id,
        crypto_profile_id=profile.id,
        result=result,
    )
    db_session.flush()
    return row


def test_shred_endpoint_destroys_key_and_audits(
    client: TestClient,
    db_session: Session,
    registered_document,
    master_key: bytes,
) -> None:
    row = _seed_ciphertext(db_session, registered_document, master_key)
    original = bytes(row.wrapped_dek)

    response = client.post(
        "/api/v1/shred",
        json={"document_id": str(registered_document.id), "confirmed": True},
        headers={"X-Q-AEGIS-Actor-Role": UserRole.COMPLIANCE_OFFICER.value},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["newly_destroyed"] == 1
    assert body["irreversible"] is True

    db_session.refresh(row)
    assert row.wrapped_dek != original
    assert is_shredded(row.wrapped_dek)
    assert row.ciphertext  # evidence retained

    events = [
        e
        for e in db_session.query(AuditLog)
        .filter(AuditLog.document_id == registered_document.id)
        .all()
        if e.event_type == AuditEventType.CRYPTO_SHREDDED.value
    ]
    assert len(events) == 1


def test_shred_requires_confirmation(
    client: TestClient, registered_document, master_key: bytes, db_session: Session
) -> None:
    _seed_ciphertext(db_session, registered_document, master_key)
    response = client.post(
        "/api/v1/shred",
        json={"document_id": str(registered_document.id), "confirmed": False},
        headers={"X-Q-AEGIS-Actor-Role": UserRole.DATA_OWNER.value},
    )
    assert response.status_code == 422


def test_shred_archives_document_status(
    client: TestClient,
    db_session: Session,
    registered_document,
    master_key: bytes,
) -> None:
    _seed_ciphertext(db_session, registered_document, master_key)
    response = client.post(
        "/api/v1/shred",
        json={"document_id": str(registered_document.id), "confirmed": True},
        headers={"X-Q-AEGIS-Actor-Role": UserRole.COMPLIANCE_OFFICER.value},
    )
    assert response.status_code == 200, response.text
    db_session.refresh(registered_document)
    from app.db.enums import DocumentStatus

    assert registered_document.current_status is DocumentStatus.ARCHIVED
