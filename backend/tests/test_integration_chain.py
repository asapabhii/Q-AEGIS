"""Master integration test for Q-AEGIS, testing the unbroken flow of a document.

Validates: document upload -> classifier -> risk engine -> trust engine ->
policy engine -> crypto selection -> crypto shredder. Ensures the audit
log maintains an unbroken cryptographic chain throughout the entire lifecycle.
"""

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import ACTOR_ROLE_HEADER
from app.api.router import API_V1_PREFIX
from app.db.enums import AuditEventType, UserRole
from app.db.models import Document, User
from app.db.repositories import audit as audit_repo

DOCUMENTS_URL = f"{API_V1_PREFIX}/documents"
CLASSIFY_URL = f"{API_V1_PREFIX}/classify"
RISK_URL = f"{API_V1_PREFIX}/risk-scores"
TRUST_URL = f"{API_V1_PREFIX}/trust-scores"
POLICY_DECISIONS_URL = f"{API_V1_PREFIX}/policy-decisions"
CRYPTO_URL = f"{API_V1_PREFIX}/crypto-profiles"
SHRED_URL = f"{API_V1_PREFIX}/crypto-shredding"

OWNER_HEADERS = {ACTOR_ROLE_HEADER: UserRole.DATA_OWNER.value}
ANALYST_HEADERS = {ACTOR_ROLE_HEADER: UserRole.SECURITY_ANALYST.value}
ADMIN_HEADERS = {ACTOR_ROLE_HEADER: UserRole.SECURITY_ADMIN.value}


def owner_user_id(session: Session) -> str:
    return str(session.query(User).filter(User.role == UserRole.DATA_OWNER).one().id)


def test_full_document_lifecycle_integration_chain(
    client: TestClient, db_session: Session
) -> None:
    """End-to-end integration test spanning all core modules."""

    # 1. Document Upload
    doc_res = client.post(
        DOCUMENTS_URL, json={"filename": "top_secret.pdf"}, headers=OWNER_HEADERS
    )
    assert doc_res.status_code == 201
    document_id = doc_res.json()["id"]

    # 2. Classifier
    cls_res = client.post(
        CLASSIFY_URL,
        json={"document_id": document_id, "content": "Confidential SSN inside."},
        headers=OWNER_HEADERS,
    )
    assert cls_res.status_code == 200

    # 3. Risk Engine
    actor_id = owner_user_id(db_session)
    risk_res = client.post(
        RISK_URL,
        json={
            "document_id": document_id,
            "actor_user_id": actor_id,
            "device_id": "laptop-12",
            "device_is_new": True,
            "accessed_at": "2026-09-09T12:00:00+00:00",
            "after_hours": True,
        },
        headers=ANALYST_HEADERS,
    )
    assert risk_res.status_code == 201
    risk_id = risk_res.json()["id"]

    # 4. Trust Engine
    trust_res = client.post(
        TRUST_URL,
        json={
            "risk_score_id": risk_id,
            "outputs": [
                {"agent_type": "security", "score": "0.50", "rationale": "ok"},
                {"agent_type": "compliance", "score": "0.50", "rationale": "ok"},
                {"agent_type": "contextual", "score": "0.50", "rationale": "ok"},
                {"agent_type": "quantum", "score": "0.50", "rationale": "ok"},
                {"agent_type": "sustainability", "score": "0.50", "rationale": "ok"},
            ],
        },
        headers=ANALYST_HEADERS,
    )
    assert trust_res.status_code == 201
    trust_id = trust_res.json()["id"]

    # 5. Policy Engine
    policy_res = client.post(
        POLICY_DECISIONS_URL,
        json={
            "trust_score_id": trust_id,
            "ai_recommendation": "allow",
        },
        headers=ADMIN_HEADERS,
    )
    assert policy_res.status_code == 201

    # 6. Crypto Selection
    crypto_res = client.post(
        CRYPTO_URL,
        json={"trust_score_id": trust_id},
        headers=ADMIN_HEADERS,
    )
    assert crypto_res.status_code == 201

    # 7. Crypto Shredder
    shred_res = client.post(
        SHRED_URL,
        json={"document_id": document_id},
        headers=OWNER_HEADERS,
    )
    assert shred_res.status_code == 200
    assert shred_res.json()["status"] == "shredded"

    # 8. Verify Audit Log Chain Integrity
    chain = audit_repo.load_chain(db_session, document_id)

    expected_events = [
        AuditEventType.DOCUMENT_REGISTERED.value,
        AuditEventType.CLASSIFICATION_COMPLETED.value,
        AuditEventType.RISK_SCORE_COMPUTED.value,
        AuditEventType.TRUST_SCORE_UPDATED.value,
        AuditEventType.POLICY_DECISION_RECORDED.value,
        AuditEventType.CRYPTO_PROFILE_SELECTED.value,
        "document_shredded",
    ]

    assert len(chain) == len(expected_events)

    # Assert sequence
    for i, event_type in enumerate(expected_events):
        assert chain[i].event_type == event_type

    # Assert unbroken cryptographic links
    for i in range(1, len(chain)):
        assert chain[i].prev_hash == chain[i - 1].payload_hash

    # 9. Verify document state
    db_session.expire_all()
    doc = db_session.get(Document, document_id)
    assert doc.current_status.value == "archived"
