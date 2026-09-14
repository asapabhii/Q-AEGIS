"""JWT auth and document upload tests."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import ACTOR_ROLE_HEADER
from app.auth.security import hash_password, verify_password
from app.db.enums import DocumentStatus, UserRole
from app.db.seed import resolve_dev_password, seed_development_users


def test_login_and_me_with_jwt(client: TestClient, db_session: Session) -> None:
    seed_development_users(db_session)
    db_session.flush()

    login = client.post(
        "/api/v1/auth/login",
        json={
            "email": "security_admin@dev.qaegis.local",
            "password": resolve_dev_password(),
        },
    )
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    assert token

    me = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert me.status_code == 200
    body = me.json()
    assert body["role"] == UserRole.SECURITY_ADMIN.value
    assert body["auth_mode"] == "jwt"


def test_dev_header_bypass_still_works(client: TestClient, db_session: Session) -> None:
    seed_development_users(db_session)
    db_session.flush()
    response = client.get(
        "/api/v1/auth/me",
        headers={ACTOR_ROLE_HEADER: UserRole.AUDITOR.value},
    )
    assert response.status_code == 200
    assert response.json()["auth_mode"] == "dev_header"


def test_login_rejects_bad_password(client: TestClient, db_session: Session) -> None:
    seed_development_users(db_session)
    db_session.flush()
    response = client.post(
        "/api/v1/auth/login",
        json={
            "email": "security_admin@dev.qaegis.local",
            "password": "definitely-wrong-password",
        },
    )
    assert response.status_code == 401


def test_upload_txt_and_classify(
    client: TestClient, db_session: Session, tmp_path: Path, monkeypatch
) -> None:
    seed_development_users(db_session)
    monkeypatch.setenv("DOCUMENT_STORAGE_DIR", str(tmp_path))
    from app.config import get_settings

    get_settings.cache_clear()

    headers = {ACTOR_ROLE_HEADER: UserRole.DATA_OWNER.value}
    registered = client.post(
        "/api/v1/documents",
        json={"filename": "notes.txt"},
        headers=headers,
    )
    assert registered.status_code == 201, registered.text
    document_id = registered.json()["id"]

    upload = client.post(
        f"/api/v1/documents/{document_id}/upload",
        headers=headers,
        files={
            "file": (
                "notes.txt",
                b"confidential secret trade secret payroll",
                "text/plain",
            )
        },
    )
    assert upload.status_code == 201, upload.text
    body = upload.json()
    assert body["current_status"] == DocumentStatus.UPLOADED.value
    assert body["extracted_text_chars"] > 0
    assert "confidential" in body["extracted_text"].lower()

    classified = client.post(
        "/api/v1/classify",
        headers=headers,
        json={
            "document_id": document_id,
            "content": body["extracted_text"],
        },
    )
    assert classified.status_code == 200, classified.text


def test_upload_rejects_oversize_without_full_buffer(
    client: TestClient, db_session: Session, tmp_path: Path, monkeypatch
) -> None:
    seed_development_users(db_session)
    monkeypatch.setenv("DOCUMENT_STORAGE_DIR", str(tmp_path))
    monkeypatch.setenv("UPLOAD_MAX_BYTES", "1024")
    from app.config import get_settings

    get_settings.cache_clear()

    headers = {ACTOR_ROLE_HEADER: UserRole.DATA_OWNER.value}
    registered = client.post(
        "/api/v1/documents",
        json={"filename": "big.bin"},
        headers=headers,
    )
    assert registered.status_code == 201, registered.text
    document_id = registered.json()["id"]

    oversized = b"x" * 2048
    upload = client.post(
        f"/api/v1/documents/{document_id}/upload",
        headers=headers,
        files={"file": ("big.bin", oversized, "application/octet-stream")},
    )
    assert upload.status_code == 413, upload.text


def test_password_hash_roundtrip() -> None:
    hashed = hash_password("local-dev-only-password")
    assert verify_password("local-dev-only-password", hashed)
    assert not verify_password("nope", hashed)


def test_agents_endpoint_empty(client: TestClient, registered_document) -> None:
    response = client.get(
        f"/api/v1/documents/{registered_document.id}/agents",
        headers={ACTOR_ROLE_HEADER: UserRole.SECURITY_ADMIN.value},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["agents"] == []
    assert body["note"]
