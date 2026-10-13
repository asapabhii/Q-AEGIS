"""Tests for the HTTP API surface.

Covers the health check, the ``POST /classify`` contract from ``SPEC.md`` 3.2,
the ``POST /risk-scores`` contract from ``SPEC.md`` 3.3, and the authorization
guard. The guard's identity source is a stub, but its fail-closed behavior is
not, so it is tested as real behavior: a missing or unrecognized role must be
refused rather than defaulted to some permitted value.

What those endpoints *persist* is tested separately in ``test_api_persistence.py``.
The policy gate (``SPEC.md`` 3.6), trust consensus (``SPEC.md`` 3.5),
crypto-profile persist (``SPEC.md`` 3.7), manual overrides (``PRD.md``
FR-12), and policy-rule dry-run (``PRD.md`` FR-13) are covered here for auth
and request validation.
"""

from decimal import Decimal
from uuid import UUID, uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.deps import ACTOR_ROLE_HEADER
from app.api.router import API_V1_PREFIX
from app.classifier.stub_classifier import MODEL_VERSION
from app.db.enums import UserRole
from app.db.models import Document, User
from app.db.models.classification import MIN_JUSTIFICATION_CHARS
from app.risk_engine.scorer import MODEL_VERSION as RISK_MODEL_VERSION

HEALTH_URL = f"{API_V1_PREFIX}/health"
DOCUMENTS_URL = f"{API_V1_PREFIX}/documents"
CLASSIFY_URL = f"{API_V1_PREFIX}/classify"
RISK_URL = f"{API_V1_PREFIX}/risk-scores"
RISK_TRIGGERS_URL = f"{API_V1_PREFIX}/risk-triggers"
POLICY_RULES_URL = f"{API_V1_PREFIX}/policy-rules"
POLICY_RULE_TEST_URL = f"{API_V1_PREFIX}/policy-rules/test"
POLICY_DECISIONS_URL = f"{API_V1_PREFIX}/policy-decisions"
TRUST_URL = f"{API_V1_PREFIX}/trust-scores"
CRYPTO_URL = f"{API_V1_PREFIX}/crypto-profiles"
OVERRIDE_URL = f"{API_V1_PREFIX}/manual-overrides"

#: A role permitted to call /classify.
OWNER_HEADERS = {ACTOR_ROLE_HEADER: UserRole.DATA_OWNER.value}

#: A role permitted to call /risk-scores.
ANALYST_HEADERS = {ACTOR_ROLE_HEADER: UserRole.SECURITY_ANALYST.value}

ADMIN_HEADERS = {ACTOR_ROLE_HEADER: UserRole.SECURITY_ADMIN.value}
AUDITOR_HEADERS = {ACTOR_ROLE_HEADER: UserRole.AUDITOR.value}


@pytest.fixture
def document_id(registered_document: Document) -> UUID:
    """The id of a document that actually exists.

    ``classification_metadata.document_id`` is a foreign key, so a classification
    request now needs a real document behind it. Requests that are expected to be
    refused before reaching the database do not use this.
    """
    return registered_document.id


def classify_body(content: str, document_id: UUID | str | None = None) -> dict:
    """Build a valid request body around ``content``."""
    reference = document_id if document_id is not None else uuid4()
    return {"document_id": str(reference), "content": content}


def risk_body(
    document_id: UUID | str,
    actor_user_id: UUID | str,
    **overrides: object,
) -> dict[str, object]:
    """Build a valid contextual-risk request body."""
    body: dict[str, object] = {
        "document_id": str(document_id),
        "actor_user_id": str(actor_user_id),
        "device_id": "laptop-12",
        "device_is_new": False,
        "accessed_at": "2026-09-09T12:00:00+00:00",
    }
    body.update(overrides)
    return body


# --------------------------------------------------------------------------
# Health check
# --------------------------------------------------------------------------


def test_health_returns_ok(client: TestClient) -> None:
    """Liveness responds 200 with the documented shape."""
    response = client.get(HEALTH_URL)
    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "ok"
    assert payload["service"] == "q-aegis-shield-backend"
    assert payload["version"]


def test_health_needs_no_credentials(client: TestClient) -> None:
    """Deliberately unauthenticated so a container runtime can probe it."""
    assert client.get(HEALTH_URL).status_code == 200


def test_health_leaks_no_dependency_or_config_detail(client: TestClient) -> None:
    """An unauthenticated endpoint must not expose runtime internals.

    This matters more now that the service does connect to Postgres: liveness must
    stay a liveness answer. Reporting datastore status here would both leak
    infrastructure detail to an unauthenticated caller and turn a database blip
    into a failed liveness probe that restarts a perfectly healthy process.
    Readiness is a separate concern and a separate endpoint when it is needed.
    """
    assert set(client.get(HEALTH_URL).json()) == {"status", "service", "version"}


# --------------------------------------------------------------------------
# Authorization guard, fails closed
# --------------------------------------------------------------------------


def test_classify_rejects_a_caller_with_no_role(client: TestClient) -> None:
    """No identity presented means refusal, not a permissive default."""
    response = client.post(CLASSIFY_URL, json=classify_body("confidential"))
    assert response.status_code == 401


@pytest.mark.parametrize("role_value", ["", "   ", "root", "admin", "DATA-OWNER"])
def test_classify_rejects_blank_or_unknown_roles(
    client: TestClient, role_value: str
) -> None:
    """Unrecognized roles are refused rather than coerced to something valid."""
    response = client.post(
        CLASSIFY_URL,
        json=classify_body("confidential"),
        headers={ACTOR_ROLE_HEADER: role_value},
    )
    assert response.status_code in (401, 403)


@pytest.mark.parametrize(
    "role",
    [UserRole.DATA_OWNER, UserRole.SECURITY_ANALYST, UserRole.SECURITY_ADMIN],
)
def test_classify_admits_permitted_roles(
    client: TestClient, document_id: UUID, role: UserRole
) -> None:
    """The three personas whose stated need involves submitting documents."""
    response = client.post(
        CLASSIFY_URL,
        json=classify_body("This document is confidential.", document_id),
        headers={ACTOR_ROLE_HEADER: role.value},
    )
    assert response.status_code == 200


@pytest.mark.parametrize(
    "role",
    [UserRole.COMPLIANCE_OFFICER, UserRole.AUDITOR, UserRole.CISO, UserRole.ENGINEER],
)
def test_classify_refuses_roles_outside_the_allow_list(
    client: TestClient, role: UserRole
) -> None:
    """Valid roles are still refused when not permitted for this action.

    Confirms the guard checks the specific allow list, not merely that the role
    parses. ``ciso`` and ``engineer`` are included because they exist in
    ``users.role`` but were not in the guard's original five, so a widened enum
    must not quietly widen access.
    """
    response = client.post(
        CLASSIFY_URL,
        json=classify_body("confidential"),
        headers={ACTOR_ROLE_HEADER: role.value},
    )
    assert response.status_code == 403


def test_role_check_is_case_insensitive(client: TestClient, document_id: UUID) -> None:
    """Header casing is a transport detail, not an authorization decision."""
    response = client.post(
        CLASSIFY_URL,
        json=classify_body("This document is confidential.", document_id),
        headers={ACTOR_ROLE_HEADER: "DATA_OWNER"},
    )
    assert response.status_code == 200


# --------------------------------------------------------------------------
# POST /classify contract, SPEC.md 3.2
# --------------------------------------------------------------------------


def test_classify_returns_the_documented_contract_fields(
    client: TestClient, document_id: UUID
) -> None:
    """``SPEC.md`` 3.2 requires these four fields on every response."""
    response = client.post(
        CLASSIFY_URL,
        json=classify_body(
            "Employee SSN, passport number, and CVV are on file.", document_id
        ),
        headers=OWNER_HEADERS,
    )
    assert response.status_code == 200
    payload = response.json()

    assert {
        "sensitivity_label",
        "confidence",
        "model_version",
        "is_defaulted",
    } <= set(payload)
    assert payload["sensitivity_label"] == "RESTRICTED"
    assert payload["is_defaulted"] is False
    assert payload["model_version"] == MODEL_VERSION


def test_classify_echoes_the_document_reference(
    client: TestClient, document_id: UUID
) -> None:
    """The response ties back to the document it describes."""
    body = classify_body("This document is confidential.", document_id)
    response = client.post(CLASSIFY_URL, json=body, headers=OWNER_HEADERS)
    assert response.json()["document_id"] == body["document_id"]


def test_classify_surfaces_the_fail_safe_escalation(
    client: TestClient, document_id: UUID
) -> None:
    """The escalation is visible over HTTP, not only inside the domain layer."""
    response = client.post(
        CLASSIFY_URL,
        json=classify_body("This document is confidential.", document_id),
        headers=OWNER_HEADERS,
    )
    payload = response.json()
    assert payload["is_defaulted"] is True
    assert payload["base_label"] == "CONFIDENTIAL"
    assert payload["sensitivity_label"] == "RESTRICTED"
    assert payload["rationale"]


def test_classify_never_returns_public_for_unrecognized_content(
    client: TestClient, document_id: UUID
) -> None:
    """The fail-safe holds at the API boundary too."""
    response = client.post(
        CLASSIFY_URL,
        json=classify_body("The quick brown fox jumps over the lazy dog.", document_id),
        headers=OWNER_HEADERS,
    )
    assert response.json()["sensitivity_label"] != "PUBLIC"


# --------------------------------------------------------------------------
# Server-side input validation, AGENTS.md
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"content": "confidential"},
        {"document_id": str(uuid4())},
        {"document_id": "not-a-uuid", "content": "confidential"},
        {"document_id": str(uuid4()), "content": ""},
        {"document_id": str(uuid4()), "content": "   "},
        {"document_id": str(uuid4()), "content": 12345},
    ],
    ids=[
        "empty-body",
        "missing-document-id",
        "missing-content",
        "malformed-uuid",
        "empty-content",
        "whitespace-only-content",
        "non-string-content",
    ],
)
def test_classify_rejects_invalid_bodies(
    client: TestClient, body: dict[str, object]
) -> None:
    """Every validation rule is enforced server-side, per ``AGENTS.md``."""
    response = client.post(CLASSIFY_URL, json=body, headers=OWNER_HEADERS)
    assert response.status_code == 422


def test_classify_rejects_unexpected_fields(
    client: TestClient, document_id: UUID
) -> None:
    """``extra="forbid"`` so a client cannot smuggle in unmodelled input."""
    body = {
        **classify_body("confidential", document_id),
        "sensitivity_label": "PUBLIC",
    }
    response = client.post(CLASSIFY_URL, json=body, headers=OWNER_HEADERS)
    assert response.status_code == 422


def test_classify_rejects_oversized_content(client: TestClient) -> None:
    """Oversized bodies are refused before reaching the keyword scan."""
    from app.classifier.schemas import MAX_CONTENT_CHARS

    body = classify_body("a" * (MAX_CONTENT_CHARS + 1))
    response = client.post(CLASSIFY_URL, json=body, headers=OWNER_HEADERS)
    assert response.status_code == 422


def test_validation_runs_even_for_an_unauthorized_caller(client: TestClient) -> None:
    """An unauthorized caller is refused regardless of body validity.

    Authorization must not be reachable only via a well-formed request.
    """
    response = client.post(CLASSIFY_URL, json={"garbage": True})
    assert response.status_code in (401, 403, 422)


# --------------------------------------------------------------------------
# Routing
# --------------------------------------------------------------------------


def test_api_is_version_prefixed(client: TestClient) -> None:
    """Endpoints live under a version prefix from the first commit."""
    assert API_V1_PREFIX == "/api/v1"
    assert client.get("/health").status_code == 404


def test_openapi_schema_is_served(client: TestClient) -> None:
    """The generated schema is the API documentation Sukhmani keeps in sync."""
    response = client.get("/openapi.json")
    assert response.status_code == 200
    paths = response.json()["paths"]
    assert HEALTH_URL in paths
    assert DOCUMENTS_URL in paths
    assert CLASSIFY_URL in paths
    assert RISK_URL in paths
    assert POLICY_RULES_URL in paths
    assert POLICY_DECISIONS_URL in paths
    assert TRUST_URL in paths
    assert CRYPTO_URL in paths
    assert f"{DOCUMENTS_URL}/{{document_id}}" in paths
    assert f"{API_V1_PREFIX}/audit/entries" in paths
    assert f"{API_V1_PREFIX}/audit/verify" in paths


# --------------------------------------------------------------------------
# GET /documents, PRD.md FR-14
# --------------------------------------------------------------------------


def test_document_inventory_rejects_a_caller_with_no_role(client: TestClient) -> None:
    assert client.get(DOCUMENTS_URL).status_code == 401


def test_document_inventory_admits_admin_analyst_and_auditor(
    client: TestClient,
) -> None:
    for headers in (ADMIN_HEADERS, ANALYST_HEADERS, AUDITOR_HEADERS):
        response = client.get(DOCUMENTS_URL, headers=headers)
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["count"] == len(payload["documents"])
        assert isinstance(payload["documents"], list)


@pytest.mark.parametrize(
    "role",
    [
        UserRole.DATA_OWNER,
        UserRole.COMPLIANCE_OFFICER,
    ],
)
def test_document_inventory_refuses_roles_outside_the_allow_list(
    client: TestClient, role: UserRole
) -> None:
    response = client.get(DOCUMENTS_URL, headers={ACTOR_ROLE_HEADER: role.value})
    assert response.status_code == 403


@pytest.mark.parametrize(
    "role",
    [UserRole.CISO, UserRole.ENGINEER],
)
def test_document_inventory_allows_ciso_and_engineer(
    client: TestClient, role: UserRole
) -> None:
    response = client.get(DOCUMENTS_URL, headers={ACTOR_ROLE_HEADER: role.value})
    assert response.status_code == 200, response.text


def test_document_inventory_item_rejects_a_caller_with_no_role(
    client: TestClient,
) -> None:
    response = client.get(f"{DOCUMENTS_URL}/{uuid4()}")
    assert response.status_code == 401


def test_document_inventory_item_unknown_id_is_404(client: TestClient) -> None:
    response = client.get(f"{DOCUMENTS_URL}/{uuid4()}", headers=ADMIN_HEADERS)
    assert response.status_code == 404


# --------------------------------------------------------------------------
# POST /risk-scores authorization, SPEC.md 3.3
# --------------------------------------------------------------------------


def test_risk_score_rejects_a_caller_with_no_role(client: TestClient) -> None:
    """No identity presented means refusal, not a permissive default."""
    response = client.post(
        RISK_URL,
        json=risk_body(uuid4(), uuid4()),
    )
    assert response.status_code == 401


@pytest.mark.parametrize(
    "role",
    [
        UserRole.SECURITY_ANALYST,
        UserRole.SECURITY_ADMIN,
    ],
)
def test_risk_score_admits_permitted_roles(
    client: TestClient,
    document_id: UUID,
    seeded_users: dict[UserRole, User],
    role: UserRole,
) -> None:
    """Analysts recompute before an override; admins recompute for the dashboard."""
    response = client.post(
        RISK_URL,
        json=risk_body(document_id, seeded_users[UserRole.DATA_OWNER].id),
        headers={ACTOR_ROLE_HEADER: role.value},
    )
    assert response.status_code == 201


@pytest.mark.parametrize(
    "role",
    [
        UserRole.DATA_OWNER,
        UserRole.COMPLIANCE_OFFICER,
        UserRole.AUDITOR,
        UserRole.CISO,
        UserRole.ENGINEER,
    ],
)
def test_risk_score_refuses_roles_outside_the_allow_list(
    client: TestClient,
    document_id: UUID,
    seeded_users: dict[UserRole, User],
    role: UserRole,
) -> None:
    """FR-13 and FR-9 do not require these personas to trigger a recompute."""
    response = client.post(
        RISK_URL,
        json=risk_body(document_id, seeded_users[UserRole.DATA_OWNER].id),
        headers={ACTOR_ROLE_HEADER: role.value},
    )
    assert response.status_code == 403


# --------------------------------------------------------------------------
# POST /risk-scores contract, SPEC.md 3.3
# --------------------------------------------------------------------------


def test_risk_score_returns_the_computed_value_not_a_client_value(
    client: TestClient,
    document_id: UUID,
    seeded_users: dict[UserRole, User],
) -> None:
    """The server owns ``risk_value``. Both signals fire: 0.20 + 0.35 + 0.25.

    ``after_hours`` is not client-supplied: the 16:00 UTC access is 21:30 in
    Asia/Kolkata, which the server derives as after-hours.
    """
    response = client.post(
        RISK_URL,
        json=risk_body(
            document_id,
            seeded_users[UserRole.DATA_OWNER].id,
            device_is_new=True,
            accessed_at="2026-09-09T16:00:00+00:00",
        ),
        headers=ANALYST_HEADERS,
    )
    assert response.status_code == 201
    payload = response.json()
    assert {
        "id",
        "document_id",
        "risk_value",
        "model_version",
        "context_snapshot",
        "computed_at",
    } <= set(payload)
    assert payload["document_id"] == str(document_id)
    assert payload["model_version"] == RISK_MODEL_VERSION
    assert Decimal(str(payload["risk_value"])) == Decimal("0.8000")
    snapshot = payload["context_snapshot"]
    assert snapshot["device_is_new"] is True
    assert snapshot["after_hours"] is True
    assert snapshot["device_id"] == "laptop-12"


@pytest.mark.parametrize(
    "body",
    [
        {},
        {"document_id": str(uuid4())},
        {
            "document_id": "not-a-uuid",
            "actor_user_id": str(uuid4()),
            "device_id": "laptop-12",
            "device_is_new": False,
            "accessed_at": "2026-09-09T12:00:00+00:00",
        },
        {
            "document_id": str(uuid4()),
            "actor_user_id": str(uuid4()),
            "device_id": "   ",
            "device_is_new": False,
            "accessed_at": "2026-09-09T12:00:00+00:00",
        },
        {
            "document_id": str(uuid4()),
            "actor_user_id": str(uuid4()),
            "device_id": "laptop-12",
            "device_is_new": False,
            "accessed_at": "2026-09-09T12:00:00",
        },
    ],
    ids=[
        "empty-body",
        "only-document-id",
        "malformed-uuid",
        "blank-device-id",
        "naive-accessed-at",
    ],
)
def test_risk_score_rejects_incomplete_or_invalid_bodies(
    client: TestClient, body: dict[str, object]
) -> None:
    """An incomplete snapshot is a 422. It never reaches the scorer."""
    response = client.post(RISK_URL, json=body, headers=ANALYST_HEADERS)
    assert response.status_code == 422


def test_risk_score_derives_after_hours_server_side(
    client: TestClient,
    document_id: UUID,
    seeded_users: dict[UserRole, User],
) -> None:
    """``after_hours`` is never a request field; the server derives it and
    returns it in the snapshot."""
    body = risk_body(document_id, seeded_users[UserRole.DATA_OWNER].id)
    response = client.post(RISK_URL, json=body, headers=ANALYST_HEADERS)
    assert response.status_code == 201, response.text
    assert "after_hours" in response.json()["context_snapshot"]


def test_risk_score_rejects_a_client_supplied_risk_value(
    client: TestClient,
    document_id: UUID,
    seeded_users: dict[UserRole, User],
) -> None:
    """``extra="forbid"`` plus no ``risk_value`` field: the server computes it."""
    body = risk_body(
        document_id, seeded_users[UserRole.DATA_OWNER].id, risk_value="0.99"
    )
    response = client.post(RISK_URL, json=body, headers=ANALYST_HEADERS)
    assert response.status_code == 422


def test_risk_score_rejects_unknown_snapshot_fields(
    client: TestClient,
    document_id: UUID,
    seeded_users: dict[UserRole, User],
) -> None:
    body = risk_body(
        document_id,
        seeded_users[UserRole.DATA_OWNER].id,
        geo_country="IN",
    )
    response = client.post(RISK_URL, json=body, headers=ANALYST_HEADERS)
    assert response.status_code == 422


# --------------------------------------------------------------------------
# POST /risk-scores subject validation, PRD.md FR-2 (third-party reporting)
# --------------------------------------------------------------------------


def test_risk_score_rejects_an_unknown_subject(
    client: TestClient,
    document_id: UUID,
) -> None:
    """A report may only name a subject the system knows.

    The document is real; the ``actor_user_id`` resolves to no registered user,
    so the request is a 404 before any score is attributed to a phantom subject.
    The document is checked first, so this exercises the subject guard, not the
    document guard.
    """
    response = client.post(
        RISK_URL,
        json=risk_body(document_id, uuid4()),
        headers=ANALYST_HEADERS,
    )
    assert response.status_code == 404, response.text
    assert "does not resolve to a registered user" in response.json()["detail"]


def test_risk_trigger_rejects_an_unknown_subject_before_publishing(
    client: TestClient,
    document_id: UUID,
) -> None:
    """FR-2 immediate recompute validates the subject before emitting anything.

    The 404 is raised in ``trigger_risk_recompute`` ahead of ``schedule_publish``,
    so an unknown subject never produces a ``risk.trigger`` event.
    """
    response = client.post(
        RISK_TRIGGERS_URL,
        json=risk_body(document_id, uuid4()),
        headers=ANALYST_HEADERS,
    )
    assert response.status_code == 404, response.text
    assert "does not resolve to a registered user" in response.json()["detail"]


def test_risk_trigger_admits_a_valid_report(
    client: TestClient,
    document_id: UUID,
    seeded_users: dict[UserRole, User],
) -> None:
    """A registered document and a resolvable subject recompute immediately.

    The response is the freshly computed score, identical in shape to
    ``POST /risk-scores``.
    """
    response = client.post(
        RISK_TRIGGERS_URL,
        json=risk_body(document_id, seeded_users[UserRole.DATA_OWNER].id),
        headers=ANALYST_HEADERS,
    )
    assert response.status_code == 201, response.text
    assert response.json()["model_version"] == RISK_MODEL_VERSION


# --------------------------------------------------------------------------
# POST /policy-rules and /policy-decisions, SPEC.md 3.6
# --------------------------------------------------------------------------


COMPLIANCE_HEADERS = {ACTOR_ROLE_HEADER: UserRole.COMPLIANCE_OFFICER.value}


def policy_rule_body(**overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "rule_name": "Deny restricted",
        "condition_expr": {
            "field": "sensitivity_label",
            "op": "eq",
            "value": "RESTRICTED",
        },
        "action": "deny",
        "priority": 10,
    }
    body.update(overrides)
    return body


def policy_decision_body(
    trust_score_id: UUID | str, **overrides: object
) -> dict[str, object]:
    body: dict[str, object] = {
        "trust_score_id": str(trust_score_id),
        "ai_recommendation": "allow",
    }
    body.update(overrides)
    return body


def test_policy_rule_rejects_a_caller_with_no_role(client: TestClient) -> None:
    response = client.post(POLICY_RULES_URL, json=policy_rule_body())
    assert response.status_code == 401


def test_policy_rule_admits_compliance_officer(client: TestClient) -> None:
    response = client.post(
        POLICY_RULES_URL, json=policy_rule_body(), headers=COMPLIANCE_HEADERS
    )
    assert response.status_code == 201


@pytest.mark.parametrize(
    "role",
    [
        UserRole.DATA_OWNER,
        UserRole.SECURITY_ANALYST,
        UserRole.SECURITY_ADMIN,
        UserRole.AUDITOR,
        UserRole.CISO,
        UserRole.ENGINEER,
    ],
)
def test_policy_rule_refuses_roles_outside_the_allow_list(
    client: TestClient, role: UserRole
) -> None:
    response = client.post(
        POLICY_RULES_URL,
        json=policy_rule_body(rule_name=f"rule-{role.value}"),
        headers={ACTOR_ROLE_HEADER: role.value},
    )
    assert response.status_code == 403


def test_policy_rule_test_rejects_a_caller_with_no_role(client: TestClient) -> None:
    response = client.post(POLICY_RULE_TEST_URL, json=policy_rule_body())
    assert response.status_code == 401


def test_policy_rule_test_admits_compliance_officer(client: TestClient) -> None:
    response = client.post(
        POLICY_RULE_TEST_URL, json=policy_rule_body(), headers=COMPLIANCE_HEADERS
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["considered"] == 0
    assert payload["skipped"] == 0
    assert payload["replays"] == []
    assert payload["window"] == 20


@pytest.mark.parametrize(
    "role",
    [
        UserRole.DATA_OWNER,
        UserRole.SECURITY_ANALYST,
        UserRole.SECURITY_ADMIN,
        UserRole.AUDITOR,
        UserRole.CISO,
        UserRole.ENGINEER,
    ],
)
def test_policy_rule_test_refuses_roles_outside_the_allow_list(
    client: TestClient, role: UserRole
) -> None:
    response = client.post(
        POLICY_RULE_TEST_URL,
        json=policy_rule_body(),
        headers={ACTOR_ROLE_HEADER: role.value},
    )
    assert response.status_code == 403


def test_policy_rule_test_rejects_a_caller_supplied_window(
    client: TestClient,
) -> None:
    body = policy_rule_body(window=5)
    response = client.post(POLICY_RULE_TEST_URL, json=body, headers=COMPLIANCE_HEADERS)
    assert response.status_code == 422


@pytest.mark.parametrize(
    "role",
    [UserRole.COMPLIANCE_OFFICER, UserRole.SECURITY_ADMIN],
)
def test_policy_decision_admits_permitted_roles(
    client: TestClient,
    document_id: UUID,
    seeded_users: dict[UserRole, User],
    role: UserRole,
) -> None:
    trust_id = assess_trust_score_id(
        client, document_id, seeded_users[UserRole.DATA_OWNER].id
    )
    response = client.post(
        POLICY_DECISIONS_URL,
        json=policy_decision_body(trust_id),
        headers={ACTOR_ROLE_HEADER: role.value},
    )
    assert response.status_code == 201, response.text
    assert response.json()["sensitivity_label"] == "RESTRICTED"
    assert response.json()["trust_score"] == "0.500"


@pytest.mark.parametrize(
    "role",
    [
        UserRole.DATA_OWNER,
        UserRole.SECURITY_ANALYST,
        UserRole.AUDITOR,
        UserRole.CISO,
        UserRole.ENGINEER,
    ],
)
def test_policy_decision_refuses_roles_outside_the_allow_list(
    client: TestClient, document_id: UUID, role: UserRole
) -> None:
    response = client.post(
        POLICY_DECISIONS_URL,
        json=policy_decision_body(document_id),
        headers={ACTOR_ROLE_HEADER: role.value},
    )
    assert response.status_code == 403


def test_policy_decision_rejects_client_supplied_final_decision(
    client: TestClient, document_id: UUID
) -> None:
    body = policy_decision_body(document_id, final_decision="deny")
    response = client.post(POLICY_DECISIONS_URL, json=body, headers=COMPLIANCE_HEADERS)
    assert response.status_code == 422


def test_policy_rule_rejects_an_unknown_operator(client: TestClient) -> None:
    body = policy_rule_body(
        condition_expr={
            "field": "sensitivity_label",
            "op": "regex",
            "value": "RESTRICTED",
        }
    )
    response = client.post(POLICY_RULES_URL, json=body, headers=COMPLIANCE_HEADERS)
    assert response.status_code == 422


def test_policy_rule_rejects_an_empty_all(client: TestClient) -> None:
    body = policy_rule_body(condition_expr={"all": []})
    response = client.post(POLICY_RULES_URL, json=body, headers=COMPLIANCE_HEADERS)
    assert response.status_code == 422


def test_policy_rule_rejects_a_tree_deeper_than_the_unrolled_rego(
    client: TestClient,
) -> None:
    tree: dict[str, object] = {
        "field": "trust_score",
        "op": "lt",
        "value": 0.5,
    }
    for _ in range(9):
        tree = {"not": tree}
    body = policy_rule_body(condition_expr=tree)
    response = client.post(POLICY_RULES_URL, json=body, headers=COMPLIANCE_HEADERS)
    assert response.status_code == 422


def test_policy_rule_rejects_a_duplicate_name(client: TestClient) -> None:
    assert (
        client.post(
            POLICY_RULES_URL, json=policy_rule_body(), headers=COMPLIANCE_HEADERS
        ).status_code
        == 201
    )
    response = client.post(
        POLICY_RULES_URL, json=policy_rule_body(), headers=COMPLIANCE_HEADERS
    )
    assert response.status_code == 409


def test_policy_rule_rejects_a_duplicate_active_priority(client: TestClient) -> None:
    assert (
        client.post(
            POLICY_RULES_URL,
            json=policy_rule_body(rule_name="first", priority=4),
            headers=COMPLIANCE_HEADERS,
        ).status_code
        == 201
    )
    response = client.post(
        POLICY_RULES_URL,
        json=policy_rule_body(rule_name="second", priority=4),
        headers=COMPLIANCE_HEADERS,
    )
    assert response.status_code == 409


def test_policy_decision_rejects_an_unknown_trust_score(client: TestClient) -> None:
    unknown = str(uuid4())
    response = client.post(
        POLICY_DECISIONS_URL,
        json=policy_decision_body(unknown),
        headers=COMPLIANCE_HEADERS,
    )
    assert response.status_code == 404
    assert "POST /api/v1/trust-scores" in response.json()["detail"]


@pytest.mark.parametrize(
    "extra",
    [
        {"risk_value": 0.1},
        {"trust_score": 0.9},
        {"sensitivity_label": "PUBLIC"},
        {"document_id": str(uuid4())},
    ],
)
def test_policy_decision_rejects_caller_supplied_facts(
    client: TestClient, extra: dict[str, object]
) -> None:
    body = policy_decision_body(uuid4(), **extra)
    response = client.post(POLICY_DECISIONS_URL, json=body, headers=COMPLIANCE_HEADERS)
    assert response.status_code == 422


def test_policy_decision_requires_a_prior_classification(
    client: TestClient,
    document_id: UUID,
    seeded_users: dict[UserRole, User],
) -> None:
    risk = client.post(
        RISK_URL,
        json=risk_body(document_id, seeded_users[UserRole.DATA_OWNER].id),
        headers=ANALYST_HEADERS,
    )
    trust = client.post(
        TRUST_URL, json=trust_body(risk.json()["id"]), headers=ANALYST_HEADERS
    )
    response = client.post(
        POLICY_DECISIONS_URL,
        json=policy_decision_body(trust.json()["id"]),
        headers=COMPLIANCE_HEADERS,
    )
    assert response.status_code == 422
    assert "POST /api/v1/classify" in response.json()["detail"]


def test_policy_rule_rejects_a_blank_name(client: TestClient) -> None:
    response = client.post(
        POLICY_RULES_URL,
        json=policy_rule_body(rule_name="   "),
        headers=COMPLIANCE_HEADERS,
    )
    assert response.status_code == 422


def test_policy_decision_returns_500_when_the_engine_fails(
    raising_client: TestClient,
    document_id: UUID,
    seeded_users: dict[UserRole, User],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.policy.engine import PolicyEngineError

    trust_id = assess_trust_score_id(
        raising_client, document_id, seeded_users[UserRole.DATA_OWNER].id
    )

    def explode(*args: object, **kwargs: object) -> None:
        raise PolicyEngineError("wasm down")

    monkeypatch.setattr("app.api.routes.policy.evaluate", explode)
    response = raising_client.post(
        POLICY_DECISIONS_URL,
        json=policy_decision_body(trust_id),
        headers=COMPLIANCE_HEADERS,
    )
    assert response.status_code == 500


def test_a_non_unique_integrity_error_is_not_mapped_to_409(
    raising_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    from sqlalchemy.exc import IntegrityError

    def boom(*args: object, **kwargs: object) -> None:
        raise IntegrityError("INSERT", {}, RuntimeError("deadlock"))

    monkeypatch.setattr("app.api.routes.policy.policy_repo.insert_rule", boom)
    response = raising_client.post(
        POLICY_RULES_URL, json=policy_rule_body(), headers=COMPLIANCE_HEADERS
    )
    assert response.status_code == 500


# --------------------------------------------------------------------------
# POST /trust-scores, SPEC.md 3.5
# --------------------------------------------------------------------------


def agent_outputs_body(**score_overrides: str) -> list[dict[str, object]]:
    scores = {
        "security": "0.50",
        "compliance": "0.50",
        "contextual": "0.50",
        "quantum": "0.50",
        "sustainability": "0.50",
    }
    scores.update(score_overrides)
    return [
        {
            "agent_type": agent,
            "score": score,
            "rationale": f"{agent} assessed this snapshot.",
        }
        for agent, score in scores.items()
    ]


def trust_body(risk_score_id: UUID | str, **overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "risk_score_id": str(risk_score_id),
        "outputs": agent_outputs_body(),
    }
    body.update(overrides)
    return body


RESTRICTED_CONTENT = "Employee SSN, passport number, and CVV are on file."


def assess_trust_score_id(
    client: TestClient,
    document_id: UUID,
    owner_user_id: UUID,
    outputs: list[dict[str, object]] | None = None,
) -> str:
    """Classify → risk → trust. Returns the trust-score id."""
    classified = client.post(
        CLASSIFY_URL,
        json=classify_body(RESTRICTED_CONTENT, document_id),
        headers=OWNER_HEADERS,
    )
    assert classified.status_code == 200, classified.text
    risk = client.post(
        RISK_URL,
        json=risk_body(document_id, owner_user_id),
        headers=ANALYST_HEADERS,
    )
    assert risk.status_code == 201, risk.text
    trust = client.post(
        TRUST_URL,
        json=trust_body(risk.json()["id"], outputs=outputs or agent_outputs_body()),
        headers=ANALYST_HEADERS,
    )
    assert trust.status_code == 201, trust.text
    return trust.json()["id"]


def test_trust_score_rejects_a_caller_with_no_role(client: TestClient) -> None:
    response = client.post(TRUST_URL, json=trust_body(uuid4()))
    assert response.status_code == 401


@pytest.mark.parametrize(
    "role",
    [UserRole.SECURITY_ANALYST, UserRole.SECURITY_ADMIN],
)
def test_trust_score_admits_permitted_roles(
    client: TestClient,
    document_id: UUID,
    seeded_users: dict[UserRole, User],
    role: UserRole,
) -> None:
    risk = client.post(
        RISK_URL,
        json=risk_body(document_id, seeded_users[UserRole.DATA_OWNER].id),
        headers=ANALYST_HEADERS,
    )
    response = client.post(
        TRUST_URL,
        json=trust_body(risk.json()["id"]),
        headers={ACTOR_ROLE_HEADER: role.value},
    )
    assert response.status_code == 201, response.text


@pytest.mark.parametrize(
    "role",
    [
        UserRole.DATA_OWNER,
        UserRole.COMPLIANCE_OFFICER,
        UserRole.AUDITOR,
        UserRole.CISO,
        UserRole.ENGINEER,
    ],
)
def test_trust_score_refuses_roles_outside_the_allow_list(
    client: TestClient, role: UserRole
) -> None:
    response = client.post(
        TRUST_URL,
        json=trust_body(uuid4()),
        headers={ACTOR_ROLE_HEADER: role.value},
    )
    assert response.status_code == 403


def test_trust_score_rejects_client_supplied_consensus(
    client: TestClient,
    document_id: UUID,
    seeded_users: dict[UserRole, User],
) -> None:
    risk = client.post(
        RISK_URL,
        json=risk_body(document_id, seeded_users[UserRole.DATA_OWNER].id),
        headers=ANALYST_HEADERS,
    )
    body = trust_body(risk.json()["id"], consensus_value="0.99")
    response = client.post(TRUST_URL, json=body, headers=ANALYST_HEADERS)
    assert response.status_code == 422


def test_trust_score_rejects_a_partial_agent_set(client: TestClient) -> None:
    body = trust_body(uuid4(), outputs=agent_outputs_body()[:4])
    response = client.post(TRUST_URL, json=body, headers=ANALYST_HEADERS)
    assert response.status_code == 422


def test_trust_score_rejects_a_duplicate_agent_type(client: TestClient) -> None:
    outputs = agent_outputs_body()
    outputs[4]["agent_type"] = "security"
    response = client.post(
        TRUST_URL, json=trust_body(uuid4(), outputs=outputs), headers=ANALYST_HEADERS
    )
    assert response.status_code == 422
    assert "Duplicate" in response.text


def test_trust_score_rejects_a_boolean_score(client: TestClient) -> None:
    outputs = agent_outputs_body()
    outputs[0]["score"] = True
    response = client.post(
        TRUST_URL, json=trust_body(uuid4(), outputs=outputs), headers=ANALYST_HEADERS
    )
    assert response.status_code == 422


def test_trust_score_rejects_a_blank_rationale(client: TestClient) -> None:
    outputs = agent_outputs_body()
    outputs[0]["rationale"] = "   "
    response = client.post(
        TRUST_URL, json=trust_body(uuid4(), outputs=outputs), headers=ANALYST_HEADERS
    )
    assert response.status_code == 422


def test_trust_score_rejects_an_unknown_risk_score(client: TestClient) -> None:
    unknown = str(uuid4())
    response = client.post(TRUST_URL, json=trust_body(unknown), headers=ANALYST_HEADERS)
    assert response.status_code == 404
    assert "POST /api/v1/risk-scores" in response.json()["detail"]


def test_trust_score_maps_an_engine_incomplete_set_to_422(
    client: TestClient,
    document_id: UUID,
    seeded_users: dict[UserRole, User],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from app.trust_engine.consensus import IncompleteAgentSetError

    risk = client.post(
        RISK_URL,
        json=risk_body(document_id, seeded_users[UserRole.DATA_OWNER].id),
        headers=ANALYST_HEADERS,
    )

    def boom(*args: object, **kwargs: object) -> None:
        raise IncompleteAgentSetError("Missing: sustainability")

    monkeypatch.setattr("app.api.routes.trust.combine", boom)
    response = client.post(
        TRUST_URL, json=trust_body(risk.json()["id"]), headers=ANALYST_HEADERS
    )
    assert response.status_code == 422


def test_a_non_unique_integrity_error_on_outputs_is_not_a_409(
    raising_client: TestClient,
    document_id: UUID,
    seeded_users: dict[UserRole, User],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from sqlalchemy.exc import IntegrityError

    risk = raising_client.post(
        RISK_URL,
        json=risk_body(document_id, seeded_users[UserRole.DATA_OWNER].id),
        headers=ANALYST_HEADERS,
    )

    def boom(*args: object, **kwargs: object) -> None:
        raise IntegrityError("INSERT", {}, RuntimeError("deadlock"))

    monkeypatch.setattr("app.api.routes.trust.trust_repo.append_agent_outputs", boom)
    response = raising_client.post(
        TRUST_URL, json=trust_body(risk.json()["id"]), headers=ANALYST_HEADERS
    )
    assert response.status_code == 500


# --------------------------------------------------------------------------
# POST /crypto-profiles, SPEC.md 3.7, PRD.md FR-6
# --------------------------------------------------------------------------


def crypto_body(trust_score_id: UUID | str, **overrides: object) -> dict[str, object]:
    body: dict[str, object] = {"trust_score_id": str(trust_score_id)}
    body.update(overrides)
    return body


def gated_trust_score_id(
    client: TestClient,
    document_id: UUID,
    owner_user_id: UUID,
    outputs: list[dict[str, object]] | None = None,
) -> str:
    """Classify → risk → trust → policy. Returns the trust-score id."""
    trust_id = assess_trust_score_id(client, document_id, owner_user_id, outputs)
    decision = client.post(
        POLICY_DECISIONS_URL,
        json=policy_decision_body(trust_id),
        headers=COMPLIANCE_HEADERS,
    )
    assert decision.status_code == 201, decision.text
    return trust_id


def test_crypto_profile_rejects_a_caller_with_no_role(client: TestClient) -> None:
    response = client.post(CRYPTO_URL, json=crypto_body(uuid4()))
    assert response.status_code == 401


@pytest.mark.parametrize(
    "role",
    [UserRole.SECURITY_ANALYST, UserRole.SECURITY_ADMIN],
)
def test_crypto_profile_admits_permitted_roles(
    client: TestClient,
    document_id: UUID,
    seeded_users: dict[UserRole, User],
    role: UserRole,
) -> None:
    trust_id = gated_trust_score_id(
        client, document_id, seeded_users[UserRole.DATA_OWNER].id
    )
    response = client.post(
        CRYPTO_URL,
        json=crypto_body(trust_id),
        headers={ACTOR_ROLE_HEADER: role.value},
    )
    assert response.status_code == 201, response.text
    assert response.json()["profile_type"] == "post_quantum"
    assert response.json()["consensus_value"] == "0.500"


@pytest.mark.parametrize(
    "role",
    [
        UserRole.DATA_OWNER,
        UserRole.COMPLIANCE_OFFICER,
        UserRole.AUDITOR,
        UserRole.CISO,
        UserRole.ENGINEER,
    ],
)
def test_crypto_profile_refuses_roles_outside_the_allow_list(
    client: TestClient, role: UserRole
) -> None:
    response = client.post(
        CRYPTO_URL,
        json=crypto_body(uuid4()),
        headers={ACTOR_ROLE_HEADER: role.value},
    )
    assert response.status_code == 403


def test_crypto_profile_rejects_client_supplied_profile_type(
    client: TestClient,
    document_id: UUID,
    seeded_users: dict[UserRole, User],
) -> None:
    trust_id = gated_trust_score_id(
        client, document_id, seeded_users[UserRole.DATA_OWNER].id
    )
    body = crypto_body(trust_id, profile_type="aes256")
    response = client.post(CRYPTO_URL, json=body, headers=ANALYST_HEADERS)
    assert response.status_code == 422


def test_crypto_profile_rejects_client_supplied_document_id(
    client: TestClient,
    document_id: UUID,
    seeded_users: dict[UserRole, User],
) -> None:
    trust_id = gated_trust_score_id(
        client, document_id, seeded_users[UserRole.DATA_OWNER].id
    )
    body = crypto_body(trust_id, document_id=str(document_id))
    response = client.post(CRYPTO_URL, json=body, headers=ANALYST_HEADERS)
    assert response.status_code == 422


def test_crypto_profile_rejects_an_unknown_trust_score(client: TestClient) -> None:
    unknown = str(uuid4())
    response = client.post(
        CRYPTO_URL, json=crypto_body(unknown), headers=ANALYST_HEADERS
    )
    assert response.status_code == 404
    assert "POST /api/v1/trust-scores" in response.json()["detail"]


def test_crypto_profile_requires_a_prior_policy_decision(
    client: TestClient,
    document_id: UUID,
    seeded_users: dict[UserRole, User],
) -> None:
    risk = client.post(
        RISK_URL,
        json=risk_body(document_id, seeded_users[UserRole.DATA_OWNER].id),
        headers=ANALYST_HEADERS,
    )
    trust = client.post(
        TRUST_URL, json=trust_body(risk.json()["id"]), headers=ANALYST_HEADERS
    )
    response = client.post(
        CRYPTO_URL, json=crypto_body(trust.json()["id"]), headers=ANALYST_HEADERS
    )
    assert response.status_code == 422
    assert "POST /api/v1/policy-decisions" in response.json()["detail"]


def test_crypto_profile_does_not_accept_another_documents_policy_decision(
    client: TestClient,
    document_id: UUID,
    seeded_users: dict[UserRole, User],
) -> None:
    """A gate evaluation on document B does not unlock selection on document A."""
    owner_id = seeded_users[UserRole.DATA_OWNER].id
    other = client.post(
        DOCUMENTS_URL, json={"filename": "other.pdf"}, headers=OWNER_HEADERS
    )
    assert other.status_code == 201, other.text
    risk = client.post(
        RISK_URL,
        json=risk_body(document_id, owner_id),
        headers=ANALYST_HEADERS,
    )
    trust = client.post(
        TRUST_URL, json=trust_body(risk.json()["id"]), headers=ANALYST_HEADERS
    )
    other_trust = assess_trust_score_id(client, other.json()["id"], owner_id)
    decision = client.post(
        POLICY_DECISIONS_URL,
        json=policy_decision_body(other_trust),
        headers=COMPLIANCE_HEADERS,
    )
    assert decision.status_code == 201, decision.text
    response = client.post(
        CRYPTO_URL, json=crypto_body(trust.json()["id"]), headers=ANALYST_HEADERS
    )
    assert response.status_code == 422


def test_crypto_profile_maps_a_selector_refusal_to_422(
    client: TestClient,
    document_id: UUID,
    seeded_users: dict[UserRole, User],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    trust_id = gated_trust_score_id(
        client, document_id, seeded_users[UserRole.DATA_OWNER].id
    )

    def boom(_score: float) -> None:
        raise ValueError("trust_score must be finite and in [0.0, 1.0]")

    monkeypatch.setattr("app.api.routes.crypto.select_crypto_profile", boom)
    response = client.post(
        CRYPTO_URL, json=crypto_body(trust_id), headers=ANALYST_HEADERS
    )
    assert response.status_code == 422


# --------------------------------------------------------------------------
# POST /manual-overrides, PRD.md FR-12
# --------------------------------------------------------------------------


def override_body(document_id: UUID | str, **overrides: object) -> dict[str, object]:
    body: dict[str, object] = {
        "document_id": str(document_id),
        "new_label": "INTERNAL",
        "justification": "Reviewed with the data owner and reclassified.",
    }
    body.update(overrides)
    return body


def test_override_rejects_a_caller_with_no_role(client: TestClient) -> None:
    response = client.post(OVERRIDE_URL, json=override_body(uuid4()))
    assert response.status_code == 401


@pytest.mark.parametrize(
    "role",
    [UserRole.SECURITY_ANALYST, UserRole.SECURITY_ADMIN],
)
def test_override_admits_permitted_roles(
    client: TestClient, document_id: UUID, role: UserRole
) -> None:
    classified = client.post(
        CLASSIFY_URL,
        json=classify_body(RESTRICTED_CONTENT, document_id),
        headers=OWNER_HEADERS,
    )
    assert classified.status_code == 200, classified.text
    response = client.post(
        OVERRIDE_URL,
        json=override_body(document_id),
        headers={ACTOR_ROLE_HEADER: role.value},
    )
    assert response.status_code == 201, response.text
    assert response.json()["original_label"] == "RESTRICTED"
    assert response.json()["new_label"] == "INTERNAL"


@pytest.mark.parametrize(
    "role",
    [
        UserRole.DATA_OWNER,
        UserRole.COMPLIANCE_OFFICER,
        UserRole.AUDITOR,
        UserRole.CISO,
        UserRole.ENGINEER,
    ],
)
def test_override_refuses_roles_outside_the_allow_list(
    client: TestClient, role: UserRole
) -> None:
    response = client.post(
        OVERRIDE_URL,
        json=override_body(uuid4()),
        headers={ACTOR_ROLE_HEADER: role.value},
    )
    assert response.status_code == 403


def test_override_rejects_a_client_supplied_original_label(
    client: TestClient, document_id: UUID
) -> None:
    body = override_body(document_id, original_label="PUBLIC")
    response = client.post(OVERRIDE_URL, json=body, headers=ANALYST_HEADERS)
    assert response.status_code == 422


def test_override_rejects_a_confirmation_boolean(
    client: TestClient, document_id: UUID
) -> None:
    """A forgeable checkbox is not evidence the analyst confirmed."""
    body = override_body(document_id, confirmed=True)
    response = client.post(OVERRIDE_URL, json=body, headers=ANALYST_HEADERS)
    assert response.status_code == 422


def test_override_rejects_a_short_justification(
    client: TestClient, document_id: UUID
) -> None:
    body = override_body(document_id, justification="x" * (MIN_JUSTIFICATION_CHARS - 1))
    response = client.post(OVERRIDE_URL, json=body, headers=ANALYST_HEADERS)
    assert response.status_code == 422


def test_override_rejects_whitespace_padding_as_the_justification_floor(
    client: TestClient, document_id: UUID
) -> None:
    padded = " " + ("x" * (MIN_JUSTIFICATION_CHARS - 1)) + " "
    body = override_body(document_id, justification=padded)
    response = client.post(OVERRIDE_URL, json=body, headers=ANALYST_HEADERS)
    assert response.status_code == 422


def test_override_unknown_document_is_404(client: TestClient) -> None:
    response = client.post(
        OVERRIDE_URL, json=override_body(uuid4()), headers=ANALYST_HEADERS
    )
    assert response.status_code == 404
    assert "POST /api/v1/documents" in response.json()["detail"]


def test_override_without_classification_is_422(
    client: TestClient, document_id: UUID
) -> None:
    response = client.post(
        OVERRIDE_URL, json=override_body(document_id), headers=ANALYST_HEADERS
    )
    assert response.status_code == 422
    assert "POST /api/v1/classify" in response.json()["detail"]


def test_override_to_the_current_label_is_422(
    client: TestClient, document_id: UUID
) -> None:
    classified = client.post(
        CLASSIFY_URL,
        json=classify_body(RESTRICTED_CONTENT, document_id),
        headers=OWNER_HEADERS,
    )
    assert classified.status_code == 200, classified.text
    response = client.post(
        OVERRIDE_URL,
        json=override_body(document_id, new_label="RESTRICTED"),
        headers=ANALYST_HEADERS,
    )
    assert response.status_code == 422
    assert "RESTRICTED" in response.json()["detail"]
