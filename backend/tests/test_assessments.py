"""API test for POST /assessments full P0 pipeline."""

from datetime import datetime, timezone
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.crypto.oqs_support import oqs_available
from app.db.enums import CryptoProfileType
from tests.test_api_persistence import (
    ANALYST_HEADERS,
    CONFIDENT_CONTENT,
    classify,
    register,
)

ASSESS_URL = "/api/v1/assessments"


def test_full_assessment_pipeline_runs_without_encrypt(
    client: TestClient, db_session: Session
) -> None:
    """Classify then assess: agents, trust, policy, profile (no ciphertext)."""
    document_id = register(client)["id"]
    assert classify(client, document_id, CONFIDENT_CONTENT).status_code == 200

    response = client.post(
        ASSESS_URL,
        json={
            "document_id": document_id,
            "device_id": "laptop-ci",
            "device_is_new": False,
            "accessed_at": datetime.now(timezone.utc).isoformat(),
            "after_hours": False,
        },
        headers=ANALYST_HEADERS,
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["document_id"] == document_id
    assert body["encrypted"] is False
    assert body["ciphertext_id"] is None
    assert body["profile_type"] in ("aes256", "hybrid", "post_quantum")
    assert body["final_decision"] in (
        "allow",
        "deny",
        "require_mfa",
        "force_pqc",
    )


def test_full_assessment_encrypts_when_profile_is_aes256(
    client: TestClient, db_session: Session
) -> None:
    """Content encrypts under AES-256 even when liboqs is absent."""
    document_id = register(client)["id"]
    assert classify(client, document_id, CONFIDENT_CONTENT).status_code == 200

    with patch(
        "app.risk_engine.pipeline.select_crypto_profile",
        return_value=CryptoProfileType.AES256,
    ):
        response = client.post(
            ASSESS_URL,
            json={
                "document_id": document_id,
                "device_id": "laptop-ci",
                "device_is_new": False,
                "accessed_at": datetime.now(timezone.utc).isoformat(),
                "after_hours": False,
                "content": CONFIDENT_CONTENT,
            },
            headers=ANALYST_HEADERS,
        )
    assert response.status_code == 201, response.text
    body = response.json()
    assert body["encrypted"] is True
    assert body["ciphertext_id"] is not None
    assert body["profile_type"] == "aes256"


def test_hybrid_encrypt_fails_closed_without_oqs(
    client: TestClient, db_session: Session
) -> None:
    """Hybrid encrypt with content refuses when liboqs is missing."""
    if oqs_available():
        return
    document_id = register(client)["id"]
    assert classify(client, document_id, CONFIDENT_CONTENT).status_code == 200

    with patch(
        "app.risk_engine.pipeline.select_crypto_profile",
        return_value=CryptoProfileType.HYBRID,
    ):
        response = client.post(
            ASSESS_URL,
            json={
                "document_id": document_id,
                "device_id": "laptop-ci",
                "device_is_new": False,
                "accessed_at": datetime.now(timezone.utc).isoformat(),
                "after_hours": False,
                "content": CONFIDENT_CONTENT,
            },
            headers=ANALYST_HEADERS,
        )
    assert response.status_code == 503
    assert "liboqs" in response.json()["detail"].lower()


def test_assessment_requires_classification(
    client: TestClient, db_session: Session
) -> None:
    document_id = register(client)["id"]
    response = client.post(
        ASSESS_URL,
        json={
            "document_id": document_id,
            "device_id": "laptop-ci",
            "device_is_new": False,
            "accessed_at": datetime.now(timezone.utc).isoformat(),
            "after_hours": False,
        },
        headers=ANALYST_HEADERS,
    )
    assert response.status_code == 422
