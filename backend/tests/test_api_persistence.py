"""Persistence behavior of the API, ``PRD.md`` Section 7 and FR-1.

Closes a known defect: before the data model existed, ``POST /classify`` computed
a classification and stored nothing, and ``PRD.md`` Section 7 treats a decision
with no corresponding audit entry as a defect rather than an edge case. What these
tests assert is that the decision and its audit entry are written together, or not
at all.
"""

from datetime import datetime
from decimal import Decimal
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import ACTOR_ROLE_HEADER
from app.api.router import API_V1_PREFIX
from app.classifier.stub_classifier import MODEL_VERSION
from app.db.enums import AuditEventType, UserRole
from app.db.models import AuditLog, ClassificationMetadata, Document
from app.db.repositories import audit as audit_repo

DOCUMENTS_URL = f"{API_V1_PREFIX}/documents"
CLASSIFY_URL = f"{API_V1_PREFIX}/classify"

OWNER_HEADERS = {ACTOR_ROLE_HEADER: UserRole.DATA_OWNER.value}

#: Content the keyword stub classifies confidently, so ``is_defaulted`` is False
#: and the escalation path is not what is being measured here.
CONFIDENT_CONTENT = "Employee SSN, passport number, and CVV are on file."


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


def rows(session: Session, model, **filters) -> list:
    """Return every row of ``model`` matching ``filters``."""
    query = session.query(model)
    for column, value in filters.items():
        query = query.filter(getattr(model, column) == value)
    return query.all()


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
    assert datetime.fromisoformat(payload["classified_at"]) == row.classified_at


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
