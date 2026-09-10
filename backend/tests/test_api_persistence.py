"""Persistence behavior of the API, ``PRD.md`` Section 7, FR-1, and FR-2.

Closes a known defect: before the data model existed, ``POST /classify`` computed
a classification and stored nothing, and ``PRD.md`` Section 7 treats a decision
with no corresponding audit entry as a defect rather than an edge case. The same
atomicity applies to ``POST /risk-scores``, the policy gate, trust-score
consensus, crypto-profile persist, and manual overrides. What these tests assert
is that the decision and its audit entry are written together, or not at all.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import ACTOR_ROLE_HEADER
from app.api.router import API_V1_PREFIX
from app.classifier.stub_classifier import MODEL_VERSION
from app.db.enums import AuditEventType, PolicyAction, SensitivityLabel, UserRole
from app.db.models import (
    AgentOutput,
    AuditLog,
    ClassificationMetadata,
    CryptoProfile,
    Document,
    ManualOverride,
    PolicyDecision,
    PolicyRule,
    RiskScore,
    TrustScore,
    User,
)
from app.db.repositories import audit as audit_repo
from app.policy.engine import POLICY_VERSION
from app.risk_engine.scorer import MODEL_VERSION as RISK_MODEL_VERSION
from app.trust_engine.consensus import CONSENSUS_VERSION

DOCUMENTS_URL = f"{API_V1_PREFIX}/documents"
CLASSIFY_URL = f"{API_V1_PREFIX}/classify"
RISK_URL = f"{API_V1_PREFIX}/risk-scores"
POLICY_RULES_URL = f"{API_V1_PREFIX}/policy-rules"
POLICY_RULE_TEST_URL = f"{API_V1_PREFIX}/policy-rules/test"
POLICY_DECISIONS_URL = f"{API_V1_PREFIX}/policy-decisions"
TRUST_URL = f"{API_V1_PREFIX}/trust-scores"
CRYPTO_URL = f"{API_V1_PREFIX}/crypto-profiles"
OVERRIDE_URL = f"{API_V1_PREFIX}/manual-overrides"

OWNER_HEADERS = {ACTOR_ROLE_HEADER: UserRole.DATA_OWNER.value}
ANALYST_HEADERS = {ACTOR_ROLE_HEADER: UserRole.SECURITY_ANALYST.value}
ADMIN_HEADERS = {ACTOR_ROLE_HEADER: UserRole.SECURITY_ADMIN.value}
COMPLIANCE_HEADERS = {ACTOR_ROLE_HEADER: UserRole.COMPLIANCE_OFFICER.value}

#: Content the keyword stub classifies confidently, so ``is_defaulted`` is False
#: and the escalation path is not what is being measured here.
CONFIDENT_CONTENT = "Employee SSN, passport number, and CVV are on file."


def as_datetime(value: str) -> datetime:
    """Parse a JSON timestamp. FastAPI writes UTC as ``Z``."""
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def register(client: TestClient, filename: str = "report.pdf") -> dict:
    """Register a document and return the response body."""
    response = client.post(
        DOCUMENTS_URL, json={"filename": filename}, headers=OWNER_HEADERS
    )
    assert response.status_code == 201, response.text
    return response.json()


def classify(client: TestClient, document_id: str, content: str = CONFIDENT_CONTENT):
    """Submit a classification request for ``document_id``."""
    return client.post(
        CLASSIFY_URL,
        json={"document_id": document_id, "content": content},
        headers=OWNER_HEADERS,
    )


def owner_user_id(session: Session) -> str:
    """The seeded Data Owner, used as the snapshot's ``actor_user_id``."""
    return str(session.query(User).filter(User.role == UserRole.DATA_OWNER).one().id)


def score_risk(
    client: TestClient,
    document_id: str,
    actor_user_id: str,
    **overrides: object,
):
    """Submit a contextual-risk request for ``document_id``."""
    body: dict[str, object] = {
        "document_id": document_id,
        "actor_user_id": actor_user_id,
        "device_id": "laptop-12",
        "device_is_new": False,
        "accessed_at": "2026-09-09T12:00:00+00:00",
        "after_hours": False,
    }
    body.update(overrides)
    return client.post(RISK_URL, json=body, headers=ANALYST_HEADERS)


def rows(session: Session, model, **filters) -> list:
    """Return every row of ``model`` matching ``filters``."""
    query = session.query(model)
    for column, value in filters.items():
        query = query.filter(getattr(model, column) == value)
    return query.all()


def inventory(client: TestClient, document_id: str | None = None):
    """Read the FR-14 inventory. List when ``document_id`` is omitted."""
    url = DOCUMENTS_URL if document_id is None else f"{DOCUMENTS_URL}/{document_id}"
    return client.get(url, headers=ADMIN_HEADERS)


# --------------------------------------------------------------------------
# POST /documents
# --------------------------------------------------------------------------


def test_registering_a_document_persists_it(
    client: TestClient, db_session: Session
) -> None:
    """The row exists, attributed to the caller's resolved user."""
    body = register(client, "invoice_Q3.pdf")

    document = db_session.get(Document, body["id"])
    assert document is not None
    assert document.filename == "invoice_Q3.pdf"
    assert document.uploaded_by is not None


def test_a_registered_document_reports_that_no_file_was_stored(
    client: TestClient,
) -> None:
    """The response does not imply an upload that did not happen.

    There is no object storage in this build, so ``storage_path`` is null and the
    status is ``registered`` rather than ``uploaded``.
    """
    body = register(client)
    assert body["storage_path"] is None
    assert body["current_status"] == "registered"


def test_registering_a_document_writes_one_audit_entry(
    client: TestClient, db_session: Session
) -> None:
    """Every state change in the pipeline produces exactly one entry."""
    body = register(client)

    entries = rows(db_session, AuditLog, document_id=body["id"])
    assert len(entries) == 1
    assert entries[0].event_type == AuditEventType.DOCUMENT_REGISTERED.value
    assert entries[0].actor_id is not None
    assert entries[0].prev_hash is None


def test_the_registration_event_does_not_claim_an_upload(
    client: TestClient, db_session: Session
) -> None:
    """``document_registered``, not ``document_uploaded``.

    The audit log is the record an auditor reads. An event name describing a file
    upload that never occurred would be a false statement in exactly the place
    that must not contain one.
    """
    body = register(client)
    entry = rows(db_session, AuditLog, document_id=body["id"])[0]
    assert entry.event_type == "document_registered"
    assert entry.payload["storage_path"] is None


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"filename": ""},
        {"filename": "   "},
        {"filename": None},
        {"name": "x.pdf"},
    ],
    ids=[
        "empty-body",
        "empty-filename",
        "blank-filename",
        "null-filename",
        "wrong-key",
    ],
)
def test_registration_validates_server_side(client: TestClient, payload: dict) -> None:
    """Every validation rule is enforced server-side, per ``AGENTS.md``."""
    response = client.post(DOCUMENTS_URL, json=payload, headers=OWNER_HEADERS)
    assert response.status_code == 422


def test_registration_refuses_a_role_outside_the_allow_list(
    client: TestClient,
) -> None:
    """An Auditor's stated need does not include submitting documents."""
    response = client.post(
        DOCUMENTS_URL,
        json={"filename": "x.pdf"},
        headers={ACTOR_ROLE_HEADER: UserRole.AUDITOR.value},
    )
    assert response.status_code == 403


# --------------------------------------------------------------------------
# POST /classify, persistence
# --------------------------------------------------------------------------


def test_classify_persists_exactly_one_classification_and_one_audit_entry(
    client: TestClient, db_session: Session
) -> None:
    """The core requirement: one decision, one record of it, no duplicates."""
    document_id = register(client)["id"]

    assert classify(client, document_id).status_code == 200

    classifications = rows(db_session, ClassificationMetadata, document_id=document_id)
    assert len(classifications) == 1

    entries = rows(db_session, AuditLog, document_id=document_id)
    classification_events = [
        entry
        for entry in entries
        if entry.event_type == AuditEventType.CLASSIFICATION_COMPLETED.value
    ]
    assert len(classification_events) == 1
    # Registration plus classification, nothing else and nothing missing.
    assert len(entries) == 2


def test_the_persisted_row_matches_the_response(
    client: TestClient, db_session: Session
) -> None:
    """``PRD.md`` FR-1 requires the model version and the fail-safe flag stored.

    Comparing against the response rather than a literal catches the case where
    both are wrong in the same way, which a hardcoded expectation would not.
    """
    document_id = register(client)["id"]
    payload = classify(client, document_id).json()

    row = rows(db_session, ClassificationMetadata, document_id=document_id)[0]
    assert row.sensitivity_label.value == payload["sensitivity_label"]
    assert row.model_version == payload["model_version"] == MODEL_VERSION
    assert row.is_defaulted is payload["is_defaulted"]
    assert row.confidence_score == Decimal(str(payload["confidence"]))


def test_the_response_timestamp_is_the_stored_one(
    client: TestClient, db_session: Session
) -> None:
    """A fresh ``datetime.now()`` in the response would disagree with the row.

    The difference would be microseconds, which is still enough for the value an
    auditor reads to not match the record it describes.
    """
    document_id = register(client)["id"]
    payload = classify(client, document_id).json()

    row = rows(db_session, ClassificationMetadata, document_id=document_id)[0]
    # Compared as instants, not strings: the JSON encoder writes the UTC offset
    # as "Z" while ``isoformat()`` writes "+00:00" for the same moment.
    assert as_datetime(payload["classified_at"]) == row.classified_at


def test_the_audit_payload_carries_the_full_decision(
    client: TestClient, db_session: Session
) -> None:
    """Including the four fields deliberately absent from the typed table.

    ``base_label``, ``confidence_threshold``, ``matched_keywords``, and
    ``rationale`` are stub artifacts or derivable, so they are not columns; they
    are kept here so explainability survives without the table accumulating them.
    """
    document_id = register(client)["id"]
    classify(client, document_id)

    entry = next(
        e
        for e in rows(db_session, AuditLog, document_id=document_id)
        if e.event_type == AuditEventType.CLASSIFICATION_COMPLETED.value
    )
    assert {
        "base_label",
        "confidence_threshold",
        "matched_keywords",
        "rationale",
        "classification_id",
    } <= set(entry.payload)


def test_the_classification_entry_links_to_the_registration_entry(
    client: TestClient, db_session: Session
) -> None:
    """One chain per document, spanning every event in its lifetime."""
    document_id = register(client)["id"]
    classify(client, document_id)

    chain = audit_repo.load_chain(db_session, document_id)
    assert [entry.event_type for entry in chain] == [
        AuditEventType.DOCUMENT_REGISTERED.value,
        AuditEventType.CLASSIFICATION_COMPLETED.value,
    ]
    assert chain[1].prev_hash == chain[0].payload_hash


def test_classification_advances_the_document_status(
    client: TestClient, db_session: Session
) -> None:
    """The lifecycle pointer moves; the decision behind it is kept separately."""
    document_id = register(client)["id"]
    classify(client, document_id)

    db_session.expire_all()
    assert db_session.get(Document, document_id).current_status.value == "classified"


def test_reclassification_appends_rather_than_overwrites(
    client: TestClient, db_session: Session
) -> None:
    """``PRD.md`` FR-1: prior classifications are superseded, never overwritten."""
    document_id = register(client)["id"]

    classify(client, document_id, "This document is confidential.")
    classify(client, document_id, CONFIDENT_CONTENT)

    classifications = rows(db_session, ClassificationMetadata, document_id=document_id)
    assert len(classifications) == 2
    assert {row.sensitivity_label.value for row in classifications} == {
        "RESTRICTED",
    } or len({row.confidence_score for row in classifications}) == 2


def test_the_latest_classification_is_retrievable(
    client: TestClient, db_session: Session
) -> None:
    """Reading back "the current label" must not depend on physical row order."""
    from app.db.repositories import classification as classification_repo

    document_id = register(client)["id"]
    classify(client, document_id)
    classify(client, document_id, "This document is confidential.")

    latest = classification_repo.latest_for_document(db_session, document_id)
    assert latest is not None


# --------------------------------------------------------------------------
# Refusals, and what they leave behind
# --------------------------------------------------------------------------


def test_classify_refuses_an_unregistered_document(client: TestClient) -> None:
    """The foreign key made this reachable; a 404 is the honest answer.

    The alternative would be inventing a ``documents`` row from a classification
    request, which would record a document nobody submitted.
    """
    response = classify(client, str(uuid4()))
    assert response.status_code == 404
    assert "POST /api/v1/documents" in response.json()["detail"]


def test_a_refused_classification_writes_nothing(
    client: TestClient, db_session: Session
) -> None:
    """A 404 must not leave a partial trace."""
    unknown = str(uuid4())
    classify(client, unknown)

    assert rows(db_session, ClassificationMetadata, document_id=unknown) == []
    assert rows(db_session, AuditLog, document_id=unknown) == []


def test_a_request_cannot_proceed_without_an_actor(
    unseeded_client: TestClient,
) -> None:
    """With no user holding the claimed role, the request is refused.

    Creating one on the fly would mean an unauthenticated request could populate
    the identity table, and a forged role header would then always resolve to
    something.
    """
    response = unseeded_client.post(
        DOCUMENTS_URL, json={"filename": "x.pdf"}, headers=OWNER_HEADERS
    )
    assert response.status_code == 503
    assert "app.db.seed" in response.json()["detail"]


def test_a_failed_audit_write_rolls_back_the_classification(
    raising_client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The atomicity guarantee, tested by breaking the second write.

    ``PRD.md`` Section 7 makes a decision without an audit entry a defect, so a
    classification that committed while its log entry failed would be the defect
    itself. Both writes share one transaction precisely so this cannot happen.
    """
    document_id = register(raising_client)["id"]

    def explode(*args: object, **kwargs: object) -> None:
        raise RuntimeError("simulated audit log failure")

    monkeypatch.setattr(audit_repo, "append_entry", explode)

    response = classify(raising_client, document_id)
    assert response.status_code == 500

    db_session.expire_all()
    assert rows(db_session, ClassificationMetadata, document_id=document_id) == []
    # The registration entry from before the patch survives; only the failed
    # request's writes are gone.
    assert len(rows(db_session, AuditLog, document_id=document_id)) == 1


# --------------------------------------------------------------------------
# POST /risk-scores, SPEC.md 3.3, PRD.md FR-2 and Section 7
# --------------------------------------------------------------------------


def test_scoring_risk_persists_the_row_and_the_audit_entry(
    client: TestClient, db_session: Session
) -> None:
    """One computation, one ``risk_scores`` row, one ``RISK_SCORE_COMPUTED`` event."""
    document_id = register(client)["id"]
    actor_id = owner_user_id(db_session)

    assert score_risk(client, document_id, actor_id).status_code == 201

    scores = rows(db_session, RiskScore, document_id=document_id)
    assert len(scores) == 1
    assert scores[0].model_version == RISK_MODEL_VERSION
    assert scores[0].risk_value == Decimal("0.2000")

    risk_events = [
        entry
        for entry in rows(db_session, AuditLog, document_id=document_id)
        if entry.event_type == AuditEventType.RISK_SCORE_COMPUTED.value
    ]
    assert len(risk_events) == 1
    assert risk_events[0].payload["model_version"] == RISK_MODEL_VERSION
    assert risk_events[0].payload["risk_value"] == "0.2000"
    assert risk_events[0].payload["risk_score_id"] == str(scores[0].id)


def test_the_persisted_risk_row_matches_the_response(
    client: TestClient, db_session: Session
) -> None:
    document_id = register(client)["id"]
    payload = score_risk(
        client,
        document_id,
        owner_user_id(db_session),
        device_is_new=True,
        after_hours=True,
    ).json()

    row = rows(db_session, RiskScore, document_id=document_id)[0]
    assert str(row.id) == payload["id"]
    assert row.model_version == payload["model_version"] == RISK_MODEL_VERSION
    assert row.risk_value == Decimal(str(payload["risk_value"])) == Decimal("0.8000")
    assert row.context_snapshot["device_id"] == "laptop-12"
    assert row.context_snapshot["device_is_new"] is True
    assert row.context_snapshot["after_hours"] is True


def test_the_risk_response_timestamp_is_the_stored_one(
    client: TestClient, db_session: Session
) -> None:
    document_id = register(client)["id"]
    payload = score_risk(client, document_id, owner_user_id(db_session)).json()
    row = rows(db_session, RiskScore, document_id=document_id)[0]
    assert as_datetime(payload["computed_at"]) == row.computed_at


def test_scoring_risk_does_not_change_document_status(
    client: TestClient, db_session: Session
) -> None:
    """Contextual risk is not a document lifecycle transition."""
    document_id = register(client)["id"]
    score_risk(client, document_id, owner_user_id(db_session))

    db_session.expire_all()
    assert db_session.get(Document, document_id).current_status.value == "registered"


def test_rescoring_appends_rather_than_overwrites(
    client: TestClient, db_session: Session
) -> None:
    document_id = register(client)["id"]
    actor_id = owner_user_id(db_session)

    score_risk(client, document_id, actor_id, device_is_new=False)
    score_risk(client, document_id, actor_id, device_is_new=True)

    scores = rows(db_session, RiskScore, document_id=document_id)
    assert len(scores) == 2
    assert {row.risk_value for row in scores} == {
        Decimal("0.2000"),
        Decimal("0.5500"),
    }
    risk_events = [
        entry
        for entry in rows(db_session, AuditLog, document_id=document_id)
        if entry.event_type == AuditEventType.RISK_SCORE_COMPUTED.value
    ]
    assert len(risk_events) == 2


def test_the_risk_entry_links_to_the_registration_entry(
    client: TestClient, db_session: Session
) -> None:
    document_id = register(client)["id"]
    score_risk(client, document_id, owner_user_id(db_session))

    chain = audit_repo.load_chain(db_session, document_id)
    assert [entry.event_type for entry in chain] == [
        AuditEventType.DOCUMENT_REGISTERED.value,
        AuditEventType.RISK_SCORE_COMPUTED.value,
    ]
    assert chain[1].prev_hash == chain[0].payload_hash


def test_risk_score_refuses_an_unregistered_document(
    client: TestClient, db_session: Session
) -> None:
    unknown = str(uuid4())
    response = score_risk(client, unknown, owner_user_id(db_session))
    assert response.status_code == 404
    assert "POST /api/v1/documents" in response.json()["detail"]

    assert rows(db_session, RiskScore, document_id=unknown) == []
    assert rows(db_session, AuditLog, document_id=unknown) == []


def test_a_failed_audit_write_rolls_back_the_risk_score(
    raising_client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A risk score with no audit entry is the Section 7 defect. Neither commits."""
    document_id = register(raising_client)["id"]
    actor_id = owner_user_id(db_session)

    def explode(*args: object, **kwargs: object) -> None:
        raise RuntimeError("simulated audit log failure")

    monkeypatch.setattr(audit_repo, "append_entry", explode)

    response = score_risk(raising_client, document_id, actor_id)
    assert response.status_code == 500

    db_session.expire_all()
    assert rows(db_session, RiskScore, document_id=document_id) == []
    assert len(rows(db_session, AuditLog, document_id=document_id)) == 1


# --------------------------------------------------------------------------
# POST /policy-rules and /policy-decisions, SPEC.md 3.6, PRD.md FR-5
# --------------------------------------------------------------------------


def test_testing_a_rule_writes_nothing(client: TestClient, db_session: Session) -> None:
    """FR-13: evaluate against history without applying the action."""
    document_id, trust_id = assess(client, db_session)
    evaluate_policy_gate(client, trust_id)
    rules_before = len(rows(db_session, PolicyRule))
    decisions_before = len(rows(db_session, PolicyDecision))
    audit_before = len(rows(db_session, AuditLog))

    response = client.post(
        POLICY_RULE_TEST_URL,
        json={
            "rule_name": "Would deny restricted",
            "condition_expr": {
                "field": "sensitivity_label",
                "op": "eq",
                "value": "RESTRICTED",
            },
            "action": "deny",
            "priority": 99,
        },
        headers=COMPLIANCE_HEADERS,
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["considered"] == 1
    assert payload["skipped"] == 0
    assert len(payload["replays"]) == 1
    replay = payload["replays"][0]
    assert replay["document_id"] == document_id
    assert replay["would_match"] is True
    assert replay["hypothetical_final_decision"] == "deny"
    assert replay["would_change_outcome"] is True
    assert replay["recorded_final_decision"] == "allow"

    assert len(rows(db_session, PolicyRule)) == rules_before
    assert len(rows(db_session, PolicyDecision)) == decisions_before
    assert len(rows(db_session, AuditLog)) == audit_before


def test_a_miss_on_history_does_not_claim_a_match(
    client: TestClient, db_session: Session
) -> None:
    _document_id, trust_id = assess(client, db_session)
    evaluate_policy_gate(client, trust_id)
    response = client.post(
        POLICY_RULE_TEST_URL,
        json={
            "rule_name": "Deny public only",
            "condition_expr": {
                "field": "sensitivity_label",
                "op": "eq",
                "value": "PUBLIC",
            },
            "action": "deny",
            "priority": 99,
        },
        headers=COMPLIANCE_HEADERS,
    )
    assert response.status_code == 200, response.text
    replay = response.json()["replays"][0]
    assert replay["would_match"] is False
    assert replay["hypothetical_final_decision"] == "allow"
    assert replay["would_change_outcome"] is False


def test_authoring_a_rule_persists_it_and_an_audit_entry(
    client: TestClient, db_session: Session
) -> None:
    response = client.post(
        POLICY_RULES_URL,
        json={
            "rule_name": "Force PQC on restricted",
            "condition_expr": {
                "field": "sensitivity_label",
                "op": "eq",
                "value": "RESTRICTED",
            },
            "action": "force_pqc",
            "priority": 3,
        },
        headers=COMPLIANCE_HEADERS,
    )
    assert response.status_code == 201, response.text
    rule_id = response.json()["id"]
    assert db_session.get(PolicyRule, rule_id) is not None
    system_events = [
        entry
        for entry in rows(db_session, AuditLog)
        if entry.event_type == AuditEventType.POLICY_RULE_CREATED.value
    ]
    assert len(system_events) == 1
    assert system_events[0].document_id is None
    assert system_events[0].payload["rule_id"] == rule_id


def test_a_matching_rule_overrides_the_ai_recommendation(
    client: TestClient, db_session: Session
) -> None:
    document_id, trust_id = assess(client, db_session)
    client.post(
        POLICY_RULES_URL,
        json={
            "rule_name": "Deny restricted documents",
            "condition_expr": {
                "field": "sensitivity_label",
                "op": "eq",
                "value": "RESTRICTED",
            },
            "action": "deny",
            "priority": 1,
        },
        headers=COMPLIANCE_HEADERS,
    )
    response = evaluate_policy_gate(client, trust_id)
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["overridden"] is True
    assert payload["final_decision"] == "deny"
    assert payload["rule_id"] is not None
    assert payload["policy_version"] == POLICY_VERSION
    assert payload["sensitivity_label"] == "RESTRICTED"
    assert payload["trust_score_id"] == trust_id
    assert Decimal(str(payload["trust_score"])) == Decimal("0.500")
    assert Decimal(str(payload["risk_value"])) == Decimal("0.2000")

    decisions = rows(db_session, PolicyDecision, document_id=document_id)
    assert len(decisions) == 1
    assert decisions[0].overridden is True
    events = [
        entry
        for entry in rows(db_session, AuditLog, document_id=document_id)
        if entry.event_type == AuditEventType.POLICY_DECISION_RECORDED.value
    ]
    assert len(events) == 1
    assert events[0].payload["overridden"] is True
    assert events[0].payload["trust_score_id"] == trust_id
    assert events[0].payload["classification_id"] == payload["classification_id"]
    assert events[0].payload["override_id"] is None
    assert events[0].payload["label_source"] == "classification"
    assert payload["override_id"] is None
    assert payload["label_source"] == "classification"


def test_no_matching_rule_leaves_the_ai_recommendation_standing(
    client: TestClient, db_session: Session
) -> None:
    _document_id, trust_id = assess(client, db_session)
    client.post(
        POLICY_RULES_URL,
        json={
            "rule_name": "Deny public only",
            "condition_expr": {
                "field": "sensitivity_label",
                "op": "eq",
                "value": "PUBLIC",
            },
            "action": "deny",
            "priority": 1,
        },
        headers=COMPLIANCE_HEADERS,
    )
    response = evaluate_policy_gate(client, trust_id)
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["rule_id"] is None
    assert payload["final_decision"] == "allow"
    assert payload["overridden"] is False


def test_inactive_rules_are_not_evaluated(
    client: TestClient, db_session: Session, seeded_users: dict
) -> None:
    from tests import factories

    document_id, trust_id = assess(client, db_session)
    factories.make_policy_rule(
        db_session,
        seeded_users[UserRole.COMPLIANCE_OFFICER].id,
        rule_name="retired deny",
        priority=1,
        active=False,
        action=PolicyAction.DENY,
    )
    db_session.flush()
    response = evaluate_policy_gate(client, trust_id)
    assert response.status_code == 201, response.text
    assert response.json()["rule_id"] is None
    assert response.json()["overridden"] is False
    assert document_id == response.json()["document_id"]


def test_a_failed_audit_write_rolls_back_the_policy_decision(
    raising_client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document_id, trust_id = assess(raising_client, db_session)

    def explode(*args: object, **kwargs: object) -> None:
        raise RuntimeError("simulated audit log failure")

    monkeypatch.setattr(audit_repo, "append_entry", explode)
    response = evaluate_policy_gate(raising_client, trust_id)
    assert response.status_code == 500
    db_session.expire_all()
    assert rows(db_session, PolicyDecision, document_id=document_id) == []


def test_the_lower_priority_active_rule_wins(
    client: TestClient, db_session: Session
) -> None:
    _document_id, trust_id = assess(client, db_session)
    later = client.post(
        POLICY_RULES_URL,
        json={
            "rule_name": "Later deny",
            "condition_expr": {
                "field": "sensitivity_label",
                "op": "eq",
                "value": "RESTRICTED",
            },
            "action": "deny",
            "priority": 20,
        },
        headers=COMPLIANCE_HEADERS,
    )
    earlier = client.post(
        POLICY_RULES_URL,
        json={
            "rule_name": "Earlier mfa",
            "condition_expr": {
                "field": "sensitivity_label",
                "op": "eq",
                "value": "RESTRICTED",
            },
            "action": "require_mfa",
            "priority": 5,
        },
        headers=COMPLIANCE_HEADERS,
    )
    assert later.status_code == 201, later.text
    assert earlier.status_code == 201, earlier.text

    response = evaluate_policy_gate(client, trust_id)
    assert response.status_code == 201, response.text
    assert response.json()["rule_id"] == earlier.json()["id"]
    assert response.json()["final_decision"] == "require_mfa"


def test_policy_evaluation_does_not_change_document_status(
    client: TestClient, db_session: Session
) -> None:
    document_id, trust_id = assess(client, db_session)
    before = db_session.get(Document, document_id).current_status
    response = evaluate_policy_gate(client, trust_id)
    assert response.status_code == 201, response.text
    db_session.expire_all()
    assert db_session.get(Document, document_id).current_status == before


def test_an_unknown_trust_score_leaves_no_policy_rows(
    client: TestClient, db_session: Session
) -> None:
    unknown = str(uuid4())
    response = evaluate_policy_gate(client, unknown)
    assert response.status_code == 404
    assert rows(db_session, PolicyDecision) == []
    assert rows(db_session, AuditLog, document_id=unknown) == []


def test_a_corrupt_stored_condition_fails_closed(
    client: TestClient, db_session: Session, seeded_users: dict
) -> None:
    """A stored tree this version cannot interpret is 422, not a skipped deny."""
    from tests import factories

    document_id, trust_id = assess(client, db_session)
    factories.make_policy_rule(
        db_session,
        seeded_users[UserRole.COMPLIANCE_OFFICER].id,
        rule_name="legacy geo deny",
        priority=1,
        condition_expr={"field": "geo_country", "op": "eq", "value": "IN"},
    )
    db_session.flush()
    response = evaluate_policy_gate(client, trust_id)
    assert response.status_code == 422
    assert rows(db_session, PolicyDecision, document_id=document_id) == []


def test_an_overdeep_stored_condition_fails_closed(
    client: TestClient, db_session: Session, seeded_users: dict
) -> None:
    from tests import factories

    document_id, trust_id = assess(client, db_session)
    tree: dict = {"field": "trust_score", "op": "lt", "value": 0.5}
    for _ in range(9):
        tree = {"not": tree}
    factories.make_policy_rule(
        db_session,
        seeded_users[UserRole.COMPLIANCE_OFFICER].id,
        rule_name="too deep",
        priority=1,
        condition_expr=tree,
    )
    db_session.flush()
    response = evaluate_policy_gate(client, trust_id)
    assert response.status_code == 422
    assert rows(db_session, PolicyDecision, document_id=document_id) == []


def test_the_latest_classification_is_the_label_the_gate_sees(
    client: TestClient, db_session: Session
) -> None:
    """A later row supersedes the first. The client cannot pick which label.

    ``classified_at`` defaults to the transaction's ``now()``, so two inserts
    in one test share a timestamp. UPDATE is refused; the newer label is
    inserted with an explicit later time.
    """
    document_id, trust_id = assess(client, db_session)
    db_session.add(
        ClassificationMetadata(
            document_id=document_id,
            sensitivity_label=SensitivityLabel.INTERNAL,
            confidence_score=Decimal("0.9000"),
            model_version="test-later-0.1.0",
            is_defaulted=False,
            classified_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    db_session.flush()
    client.post(
        POLICY_RULES_URL,
        json={
            "rule_name": "Deny restricted after reclassify",
            "condition_expr": {
                "field": "sensitivity_label",
                "op": "eq",
                "value": "RESTRICTED",
            },
            "action": "deny",
            "priority": 2,
        },
        headers=COMPLIANCE_HEADERS,
    )
    response = evaluate_policy_gate(client, trust_id)
    assert response.status_code == 201, response.text
    assert response.json()["sensitivity_label"] == "INTERNAL"
    assert response.json()["final_decision"] == "allow"
    assert response.json()["overridden"] is False


def test_the_stored_trust_score_is_what_the_gate_compares(
    client: TestClient, db_session: Session
) -> None:
    """Equal-weight 0.500 matches lt 0.6. A caller cannot send 0.9 instead."""
    _document_id, trust_id = assess(client, db_session, score="0.50")
    client.post(
        POLICY_RULES_URL,
        json={
            "rule_name": "MFA below 0.6 trust",
            "condition_expr": {"field": "trust_score", "op": "lt", "value": 0.6},
            "action": "require_mfa",
            "priority": 4,
        },
        headers=COMPLIANCE_HEADERS,
    )
    refused = client.post(
        POLICY_DECISIONS_URL,
        json={
            "trust_score_id": trust_id,
            "ai_recommendation": "allow",
            "trust_score": 0.9,
        },
        headers=COMPLIANCE_HEADERS,
    )
    assert refused.status_code == 422
    response = evaluate_policy_gate(client, trust_id)
    assert response.status_code == 201, response.text
    assert response.json()["final_decision"] == "require_mfa"


def test_a_missing_linked_risk_score_fails_closed(
    client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _document_id, trust_id = assess(client, db_session)
    monkeypatch.setattr(
        "app.api.routes.policy.risk_repo.get_risk_score", lambda *args, **kwargs: None
    )
    response = evaluate_policy_gate(client, trust_id)
    assert response.status_code == 422
    assert "POST /api/v1/risk-scores" in response.json()["detail"]


def test_a_trust_row_pointing_at_another_documents_risk_fails_closed(
    client: TestClient, db_session: Session
) -> None:
    from tests import factories

    document_id, _trust_id = assess(client, db_session)
    other_id, _other_trust = assess(client, db_session)
    document = db_session.get(Document, document_id)
    other_risk = rows(db_session, RiskScore, document_id=other_id)[0]
    mismatched = factories.make_trust_score(db_session, document, other_risk)
    db_session.flush()
    response = evaluate_policy_gate(client, str(mismatched.id))
    assert response.status_code == 422
    assert "different document" in response.json()["detail"]


def test_trust_without_classification_leaves_no_policy_rows(
    client: TestClient, db_session: Session
) -> None:
    document_id = register(client)["id"]
    risk_id = score_risk(client, document_id, owner_user_id(db_session)).json()["id"]
    trust = compute_trust(client, risk_id)
    assert trust.status_code == 201, trust.text
    response = evaluate_policy_gate(client, trust.json()["id"])
    assert response.status_code == 422
    assert rows(db_session, PolicyDecision, document_id=document_id) == []


def test_a_failed_audit_write_rolls_back_the_new_rule(
    raising_client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def explode(*args: object, **kwargs: object) -> None:
        raise RuntimeError("simulated audit log failure")

    monkeypatch.setattr(audit_repo, "append_entry", explode)
    response = raising_client.post(
        POLICY_RULES_URL,
        json={
            "rule_name": "Never committed",
            "condition_expr": {
                "field": "sensitivity_label",
                "op": "eq",
                "value": "RESTRICTED",
            },
            "action": "deny",
            "priority": 7,
        },
        headers=COMPLIANCE_HEADERS,
    )
    assert response.status_code == 500
    db_session.expire_all()
    assert rows(db_session, PolicyRule, rule_name="Never committed") == []


# --------------------------------------------------------------------------
# POST /trust-scores, SPEC.md 3.5, PRD.md FR-4
# --------------------------------------------------------------------------


def five_agent_outputs(score: str = "0.50") -> list[dict[str, object]]:
    return [
        {
            "agent_type": agent,
            "score": score,
            "rationale": f"{agent} assessed this snapshot.",
        }
        for agent in (
            "security",
            "compliance",
            "contextual",
            "quantum",
            "sustainability",
        )
    ]


def compute_trust(client: TestClient, risk_id: str, score: str = "0.50"):
    """Submit a trust-score request for ``risk_id``."""
    return client.post(
        TRUST_URL,
        json={"risk_score_id": risk_id, "outputs": five_agent_outputs(score)},
        headers=ANALYST_HEADERS,
    )


def evaluate_policy_gate(client: TestClient, trust_score_id: str):
    """Evaluate the gate from a persisted trust score."""
    return client.post(
        POLICY_DECISIONS_URL,
        json={
            "trust_score_id": trust_score_id,
            "ai_recommendation": "allow",
        },
        headers=COMPLIANCE_HEADERS,
    )


def assess(
    client: TestClient,
    db_session: Session,
    *,
    content: str = CONFIDENT_CONTENT,
    score: str = "0.50",
) -> tuple[str, str]:
    """Register → classify → risk → trust. Returns ``(document_id, trust_id)``."""
    document_id = register(client)["id"]
    assert classify(client, document_id, content).status_code == 200
    risk_id = score_risk(client, document_id, owner_user_id(db_session)).json()["id"]
    trust = compute_trust(client, risk_id, score)
    assert trust.status_code == 201, trust.text
    return document_id, trust.json()["id"]


def select_crypto(client: TestClient, trust_score_id: str):
    """Persist a protection profile from ``trust_score_id``."""
    return client.post(
        CRYPTO_URL,
        json={"trust_score_id": trust_score_id},
        headers=ANALYST_HEADERS,
    )


def gated_trust(
    client: TestClient, db_session: Session, score: str = "0.50"
) -> tuple[str, str]:
    """Classify through policy. Returns ``(document_id, trust_id)``."""
    document_id, trust_id = assess(client, db_session, score=score)
    gate = evaluate_policy_gate(client, trust_id)
    assert gate.status_code == 201, gate.text
    return document_id, trust_id


def test_computing_trust_persists_outputs_the_row_and_the_audit_entry(
    client: TestClient, db_session: Session
) -> None:
    document_id = register(client)["id"]
    risk_id = score_risk(client, document_id, owner_user_id(db_session)).json()["id"]

    response = client.post(
        TRUST_URL,
        json={"risk_score_id": risk_id, "outputs": five_agent_outputs()},
        headers=ANALYST_HEADERS,
    )
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["consensus_value"] == "0.500"
    assert payload["consensus_version"] == CONSENSUS_VERSION
    assert payload["document_id"] == document_id
    assert payload["risk_score_id"] == risk_id
    assert len(payload["outputs"]) == 5

    assert len(rows(db_session, TrustScore, document_id=document_id)) == 1
    assert len(rows(db_session, AgentOutput, risk_score_id=risk_id)) == 5
    events = [
        entry
        for entry in rows(db_session, AuditLog, document_id=document_id)
        if entry.event_type == AuditEventType.TRUST_SCORE_UPDATED.value
    ]
    assert len(events) == 1
    assert events[0].payload["consensus_version"] == CONSENSUS_VERSION
    assert events[0].payload["trust_score_id"] == payload["id"]
    assert len(events[0].payload["agent_output_ids"]) == 5


def test_a_second_consensus_on_the_same_risk_score_is_a_conflict(
    client: TestClient, db_session: Session
) -> None:
    document_id = register(client)["id"]
    risk_id = score_risk(client, document_id, owner_user_id(db_session)).json()["id"]
    body = {"risk_score_id": risk_id, "outputs": five_agent_outputs()}
    assert client.post(TRUST_URL, json=body, headers=ANALYST_HEADERS).status_code == 201
    response = client.post(TRUST_URL, json=body, headers=ANALYST_HEADERS)
    assert response.status_code == 409
    assert len(rows(db_session, TrustScore, document_id=document_id)) == 1


def test_trust_evaluation_does_not_change_document_status(
    client: TestClient, db_session: Session
) -> None:
    document_id = register(client)["id"]
    before = db_session.get(Document, document_id).current_status
    risk_id = score_risk(client, document_id, owner_user_id(db_session)).json()["id"]
    response = client.post(
        TRUST_URL,
        json={"risk_score_id": risk_id, "outputs": five_agent_outputs()},
        headers=ANALYST_HEADERS,
    )
    assert response.status_code == 201, response.text
    db_session.expire_all()
    assert db_session.get(Document, document_id).current_status == before


def test_an_unknown_risk_score_leaves_no_trust_rows(
    client: TestClient, db_session: Session
) -> None:
    unknown = str(uuid4())
    response = client.post(
        TRUST_URL,
        json={"risk_score_id": unknown, "outputs": five_agent_outputs()},
        headers=ANALYST_HEADERS,
    )
    assert response.status_code == 404
    assert rows(db_session, TrustScore) == []
    assert rows(db_session, AgentOutput) == []


def test_a_failed_audit_write_rolls_back_the_trust_score(
    raising_client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document_id = register(raising_client)["id"]
    risk_id = score_risk(raising_client, document_id, owner_user_id(db_session)).json()[
        "id"
    ]

    def explode(*args: object, **kwargs: object) -> None:
        raise RuntimeError("simulated audit log failure")

    monkeypatch.setattr(audit_repo, "append_entry", explode)
    response = raising_client.post(
        TRUST_URL,
        json={"risk_score_id": risk_id, "outputs": five_agent_outputs()},
        headers=ANALYST_HEADERS,
    )
    assert response.status_code == 500
    db_session.expire_all()
    assert rows(db_session, TrustScore, document_id=document_id) == []
    assert rows(db_session, AgentOutput, risk_score_id=risk_id) == []


# --------------------------------------------------------------------------
# POST /crypto-profiles, SPEC.md 3.7, PRD.md FR-6
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "score, expected",
    [
        ("0.20", "post_quantum"),
        ("0.40", "post_quantum"),
        ("0.50", "hybrid"),
        ("0.80", "hybrid"),
        ("0.90", "aes256"),
    ],
)
def test_selecting_a_crypto_profile_persists_the_row_and_the_audit_entry(
    client: TestClient, db_session: Session, score: str, expected: str
) -> None:
    document_id, trust_id = gated_trust(client, db_session, score)

    response = select_crypto(client, trust_id)
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["document_id"] == document_id
    assert payload["trust_score_id"] == trust_id
    assert payload["profile_type"] == expected
    assert Decimal(str(payload["consensus_value"])) == Decimal(score)

    profiles = rows(db_session, CryptoProfile, document_id=document_id)
    assert len(profiles) == 1
    assert profiles[0].profile_type.value == expected
    assert str(profiles[0].trust_score_id) == trust_id
    events = [
        entry
        for entry in rows(db_session, AuditLog, document_id=document_id)
        if entry.event_type == AuditEventType.CRYPTO_PROFILE_SELECTED.value
    ]
    assert len(events) == 1
    assert events[0].payload["profile_type"] == expected
    assert events[0].payload["trust_score_id"] == trust_id
    assert Decimal(str(events[0].payload["consensus_value"])) == Decimal(score)
    assert events[0].payload["post_quantum_max"] == "0.4"
    assert events[0].payload["hybrid_max"] == "0.8"


def test_reselecting_a_crypto_profile_appends_a_new_row(
    client: TestClient, db_session: Session
) -> None:
    document_id, trust_id = gated_trust(client, db_session)
    first = select_crypto(client, trust_id)
    second = select_crypto(client, trust_id)
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["id"] != second.json()["id"]
    assert len(rows(db_session, CryptoProfile, document_id=document_id)) == 2


def test_a_deny_policy_decision_still_allows_crypto_persist(
    client: TestClient, db_session: Session
) -> None:
    """The gate already recorded; this table is separate history."""
    document_id, trust_id = assess(client, db_session)
    rule = client.post(
        POLICY_RULES_URL,
        json={
            "rule_name": "Deny restricted for crypto persist",
            "condition_expr": {
                "field": "sensitivity_label",
                "op": "eq",
                "value": "RESTRICTED",
            },
            "action": "deny",
            "priority": 3,
        },
        headers=COMPLIANCE_HEADERS,
    )
    assert rule.status_code == 201, rule.text
    gate = evaluate_policy_gate(client, trust_id)
    assert gate.status_code == 201, gate.text
    assert gate.json()["final_decision"] == "deny"
    response = select_crypto(client, trust_id)
    assert response.status_code == 201, response.text
    assert document_id == gate.json()["document_id"]


def test_selecting_a_crypto_profile_does_not_change_document_status(
    client: TestClient, db_session: Session
) -> None:
    document_id, trust_id = gated_trust(client, db_session)
    before = db_session.get(Document, document_id).current_status
    response = select_crypto(client, trust_id)
    assert response.status_code == 201, response.text
    db_session.expire_all()
    assert db_session.get(Document, document_id).current_status == before


def test_an_unknown_trust_score_leaves_no_crypto_rows(
    client: TestClient, db_session: Session
) -> None:
    unknown = str(uuid4())
    response = select_crypto(client, unknown)
    assert response.status_code == 404
    assert rows(db_session, CryptoProfile) == []
    assert rows(db_session, AuditLog, document_id=unknown) == []


def test_trust_without_a_policy_decision_leaves_no_crypto_rows(
    client: TestClient, db_session: Session
) -> None:
    document_id = register(client)["id"]
    risk_id = score_risk(client, document_id, owner_user_id(db_session)).json()["id"]
    trust = compute_trust(client, risk_id)
    assert trust.status_code == 201, trust.text
    response = select_crypto(client, trust.json()["id"])
    assert response.status_code == 422
    assert rows(db_session, CryptoProfile, document_id=document_id) == []
    events = [
        entry
        for entry in rows(db_session, AuditLog, document_id=document_id)
        if entry.event_type == AuditEventType.CRYPTO_PROFILE_SELECTED.value
    ]
    assert events == []


def test_a_failed_audit_write_rolls_back_the_crypto_profile(
    raising_client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document_id, trust_id = gated_trust(raising_client, db_session)

    def explode(*args: object, **kwargs: object) -> None:
        raise RuntimeError("simulated audit log failure")

    monkeypatch.setattr(audit_repo, "append_entry", explode)
    response = raising_client.post(
        CRYPTO_URL,
        json={"trust_score_id": trust_id},
        headers=ANALYST_HEADERS,
    )
    assert response.status_code == 500
    db_session.expire_all()
    assert rows(db_session, CryptoProfile, document_id=document_id) == []


# --------------------------------------------------------------------------
# POST /manual-overrides, PRD.md FR-12
# --------------------------------------------------------------------------


OVERRIDE_JUSTIFICATION = "Reviewed with the data owner and reclassified."


def override_label(
    client: TestClient,
    document_id: str,
    new_label: str = "INTERNAL",
    justification: str = OVERRIDE_JUSTIFICATION,
):
    """Persist a manual override for ``document_id``."""
    return client.post(
        OVERRIDE_URL,
        json={
            "document_id": document_id,
            "new_label": new_label,
            "justification": justification,
        },
        headers=ANALYST_HEADERS,
    )


def test_overriding_persists_the_row_and_the_audit_entry(
    client: TestClient, db_session: Session
) -> None:
    document_id = register(client)["id"]
    assert classify(client, document_id).status_code == 200

    response = override_label(client, document_id)
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["original_label"] == "RESTRICTED"
    assert payload["new_label"] == "INTERNAL"
    assert payload["justification"] == OVERRIDE_JUSTIFICATION

    overrides = rows(db_session, ManualOverride, document_id=document_id)
    assert len(overrides) == 1
    assert overrides[0].original_label.value == "RESTRICTED"
    assert overrides[0].new_label.value == "INTERNAL"
    events = [
        entry
        for entry in rows(db_session, AuditLog, document_id=document_id)
        if entry.event_type == AuditEventType.MANUAL_OVERRIDE.value
    ]
    assert len(events) == 1
    assert events[0].payload["override_id"] == payload["id"]
    assert events[0].payload["original_label"] == "RESTRICTED"
    assert events[0].payload["new_label"] == "INTERNAL"


def test_a_failed_audit_write_rolls_back_the_override(
    raising_client: TestClient,
    db_session: Session,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document_id = register(raising_client)["id"]
    assert classify(raising_client, document_id).status_code == 200

    def explode(*args: object, **kwargs: object) -> None:
        raise RuntimeError("simulated audit log failure")

    monkeypatch.setattr(audit_repo, "append_entry", explode)
    response = override_label(raising_client, document_id)
    assert response.status_code == 500
    db_session.expire_all()
    assert rows(db_session, ManualOverride, document_id=document_id) == []


def test_override_does_not_change_document_status(
    client: TestClient, db_session: Session
) -> None:
    document_id = register(client)["id"]
    assert classify(client, document_id).status_code == 200
    before = db_session.get(Document, document_id).current_status
    response = override_label(client, document_id)
    assert response.status_code == 201, response.text
    db_session.expire_all()
    assert db_session.get(Document, document_id).current_status == before


def test_a_second_override_snapshots_the_previous_effective_label(
    client: TestClient, db_session: Session
) -> None:
    document_id = register(client)["id"]
    assert classify(client, document_id).status_code == 200
    first = override_label(client, document_id, new_label="INTERNAL")
    assert first.status_code == 201, first.text
    second = override_label(client, document_id, new_label="PUBLIC")
    assert second.status_code == 201, second.text
    assert second.json()["original_label"] == "INTERNAL"
    assert second.json()["new_label"] == "PUBLIC"
    assert len(rows(db_session, ManualOverride, document_id=document_id)) == 2


def test_the_gate_sees_the_override_not_the_ai_label(
    client: TestClient, db_session: Session
) -> None:
    document_id, trust_id = assess(client, db_session)
    overridden = override_label(client, document_id, new_label="INTERNAL")
    assert overridden.status_code == 201, overridden.text
    client.post(
        POLICY_RULES_URL,
        json={
            "rule_name": "Deny restricted after override",
            "condition_expr": {
                "field": "sensitivity_label",
                "op": "eq",
                "value": "RESTRICTED",
            },
            "action": "deny",
            "priority": 7,
        },
        headers=COMPLIANCE_HEADERS,
    )
    response = evaluate_policy_gate(client, trust_id)
    assert response.status_code == 201, response.text
    payload = response.json()
    assert payload["sensitivity_label"] == "INTERNAL"
    assert payload["override_id"] == overridden.json()["id"]
    assert payload["label_source"] == "manual_override"
    assert payload["final_decision"] == "allow"
    assert payload["overridden"] is False
    events = [
        entry
        for entry in rows(db_session, AuditLog, document_id=document_id)
        if entry.event_type == AuditEventType.POLICY_DECISION_RECORDED.value
    ]
    assert events[0].payload["override_id"] == overridden.json()["id"]
    assert events[0].payload["label_source"] == "manual_override"
    assert events[0].payload["sensitivity_label"] == "INTERNAL"


def test_a_later_classification_does_not_undo_the_override_at_the_gate(
    client: TestClient, db_session: Session
) -> None:
    document_id, trust_id = assess(client, db_session)
    assert override_label(client, document_id, new_label="INTERNAL").status_code == 201
    db_session.add(
        ClassificationMetadata(
            document_id=document_id,
            sensitivity_label=SensitivityLabel.RESTRICTED,
            confidence_score=Decimal("0.9000"),
            model_version="test-later-0.1.0",
            is_defaulted=False,
            classified_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    db_session.flush()
    client.post(
        POLICY_RULES_URL,
        json={
            "rule_name": "Deny restricted after reclassify under override",
            "condition_expr": {
                "field": "sensitivity_label",
                "op": "eq",
                "value": "RESTRICTED",
            },
            "action": "deny",
            "priority": 8,
        },
        headers=COMPLIANCE_HEADERS,
    )
    response = evaluate_policy_gate(client, trust_id)
    assert response.status_code == 201, response.text
    assert response.json()["sensitivity_label"] == "INTERNAL"
    assert response.json()["label_source"] == "manual_override"
    assert response.json()["final_decision"] == "allow"


# --------------------------------------------------------------------------
# Full decision path, SPEC.md Section 4
# --------------------------------------------------------------------------


def test_the_classify_to_crypto_chain_writes_every_decision_and_its_audit(
    client: TestClient, db_session: Session
) -> None:
    """Classify → risk → trust → policy → crypto, each with an audit entry."""
    document_id, trust_id = assess(client, db_session, score="0.50")
    gate = evaluate_policy_gate(client, trust_id)
    assert gate.status_code == 201, gate.text
    assert gate.json()["sensitivity_label"] == "RESTRICTED"
    assert Decimal(str(gate.json()["trust_score"])) == Decimal("0.500")

    profile = select_crypto(client, trust_id)
    assert profile.status_code == 201, profile.text
    assert profile.json()["profile_type"] == "hybrid"

    events = {
        entry.event_type
        for entry in rows(db_session, AuditLog, document_id=document_id)
    }
    assert AuditEventType.CLASSIFICATION_COMPLETED.value in events
    assert AuditEventType.RISK_SCORE_COMPUTED.value in events
    assert AuditEventType.TRUST_SCORE_UPDATED.value in events
    assert AuditEventType.POLICY_DECISION_RECORDED.value in events
    assert AuditEventType.CRYPTO_PROFILE_SELECTED.value in events
    assert rows(db_session, ClassificationMetadata, document_id=document_id)
    assert rows(db_session, RiskScore, document_id=document_id)
    assert rows(db_session, TrustScore, document_id=document_id)
    assert rows(db_session, PolicyDecision, document_id=document_id)
    assert rows(db_session, CryptoProfile, document_id=document_id)


# --------------------------------------------------------------------------
# GET /documents, PRD.md FR-14
# --------------------------------------------------------------------------


def test_a_registered_document_has_null_stage_fields(
    client: TestClient,
) -> None:
    document_id = register(client)["id"]
    response = inventory(client, document_id)
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["id"] == document_id
    assert payload["current_status"] == "registered"
    assert payload["sensitivity_label"] is None
    assert payload["label_source"] is None
    assert payload["override_id"] is None
    assert payload["classification_id"] is None
    assert payload["risk_score_id"] is None
    assert payload["risk_value"] is None
    assert payload["trust_score_id"] is None
    assert payload["trust_score"] is None
    assert payload["policy_decision_id"] is None
    assert payload["final_decision"] is None
    assert payload["crypto_profile_id"] is None
    assert payload["profile_type"] is None


def test_inventory_list_and_item_agree(client: TestClient) -> None:
    first = register(client, filename="one.pdf")["id"]
    second = register(client, filename="two.pdf")["id"]
    listed = inventory(client)
    assert listed.status_code == 200, listed.text
    payload = listed.json()
    assert payload["count"] == 2
    ids = {item["id"] for item in payload["documents"]}
    assert ids == {first, second}
    item = inventory(client, first)
    assert item.status_code == 200, item.text
    listed_first = next(row for row in payload["documents"] if row["id"] == first)
    assert item.json() == listed_first


def test_inventory_reads_the_effective_label_not_a_later_classification(
    client: TestClient,
) -> None:
    document_id = register(client)["id"]
    assert classify(client, document_id).status_code == 200
    overridden = override_label(client, document_id)
    assert overridden.status_code == 201, overridden.text
    assert classify(client, document_id).status_code == 200

    payload = inventory(client, document_id).json()
    assert payload["sensitivity_label"] == "INTERNAL"
    assert payload["label_source"] == "manual_override"
    assert payload["override_id"] == overridden.json()["id"]
    assert payload["classification_id"] is not None


def test_inventory_reads_the_latest_risk_score(
    client: TestClient, db_session: Session
) -> None:
    document_id = register(client)["id"]
    actor = owner_user_id(db_session)
    first = score_risk(client, document_id, actor)
    assert first.status_code == 201, first.text
    second = score_risk(client, document_id, actor, after_hours=True)
    assert second.status_code == 201, second.text
    payload = inventory(client, document_id).json()
    assert payload["risk_score_id"] == second.json()["id"]
    assert Decimal(str(payload["risk_value"])) == Decimal("0.4500")
    assert payload["risk_score_id"] != first.json()["id"]


def test_inventory_reads_the_full_protection_snapshot(
    client: TestClient, db_session: Session
) -> None:
    document_id, trust_id = gated_trust(client, db_session, score="0.50")
    profile = select_crypto(client, trust_id)
    assert profile.status_code == 201, profile.text
    payload = inventory(client, document_id).json()
    assert payload["sensitivity_label"] == "RESTRICTED"
    assert payload["label_source"] == "classification"
    assert payload["trust_score_id"] == trust_id
    assert Decimal(str(payload["trust_score"])) == Decimal("0.500")
    assert payload["final_decision"] == "allow"
    assert payload["profile_type"] == "hybrid"
    assert payload["crypto_profile_id"] == profile.json()["id"]
    assert payload["policy_decision_id"] is not None
    assert payload["risk_score_id"] is not None
    listed = inventory(client).json()
    row = next(item for item in listed["documents"] if item["id"] == document_id)
    assert row == payload


def test_reading_the_inventory_writes_nothing(
    client: TestClient, db_session: Session
) -> None:
    document_id, _trust_id = assess(client, db_session)
    rules_before = len(rows(db_session, PolicyRule))
    decisions_before = len(rows(db_session, PolicyDecision))
    audit_before = len(rows(db_session, AuditLog))
    documents_before = len(rows(db_session, Document))

    assert inventory(client).status_code == 200
    assert inventory(client, document_id).status_code == 200

    assert len(rows(db_session, PolicyRule)) == rules_before
    assert len(rows(db_session, PolicyDecision)) == decisions_before
    assert len(rows(db_session, AuditLog)) == audit_before
    assert len(rows(db_session, Document)) == documents_before
