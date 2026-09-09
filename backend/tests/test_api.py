"""Tests for the HTTP API surface.

Covers the health check, the ``POST /classify`` contract from ``SPEC.md`` 3.2,
the ``POST /risk-scores`` contract from ``SPEC.md`` 3.3, and the authorization
guard. The guard's identity source is a stub, but its fail-closed behavior is
not, so it is tested as real behavior: a missing or unrecognized role must be
refused rather than defaulted to some permitted value.

What those endpoints *persist* is tested separately in ``test_api_persistence.py``.
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
from app.risk_engine.scorer import MODEL_VERSION as RISK_MODEL_VERSION

HEALTH_URL = f"{API_V1_PREFIX}/health"
DOCUMENTS_URL = f"{API_V1_PREFIX}/documents"
CLASSIFY_URL = f"{API_V1_PREFIX}/classify"
RISK_URL = f"{API_V1_PREFIX}/risk-scores"

#: A role permitted to call /classify.
OWNER_HEADERS = {ACTOR_ROLE_HEADER: UserRole.DATA_OWNER.value}

#: A role permitted to call /risk-scores.
ANALYST_HEADERS = {ACTOR_ROLE_HEADER: UserRole.SECURITY_ANALYST.value}


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
        "after_hours": False,
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
    """The server owns ``risk_value``. Both signals fire: 0.20 + 0.35 + 0.25."""
    response = client.post(
        RISK_URL,
        json=risk_body(
            document_id,
            seeded_users[UserRole.DATA_OWNER].id,
            device_is_new=True,
            after_hours=True,
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
            "document_id": str(uuid4()),
            "actor_user_id": str(uuid4()),
            "device_id": "laptop-12",
            "device_is_new": True,
            "accessed_at": "2026-09-09T12:00:00+00:00",
        },
        {
            "document_id": "not-a-uuid",
            "actor_user_id": str(uuid4()),
            "device_id": "laptop-12",
            "device_is_new": False,
            "accessed_at": "2026-09-09T12:00:00+00:00",
            "after_hours": False,
        },
        {
            "document_id": str(uuid4()),
            "actor_user_id": str(uuid4()),
            "device_id": "   ",
            "device_is_new": False,
            "accessed_at": "2026-09-09T12:00:00+00:00",
            "after_hours": False,
        },
        {
            "document_id": str(uuid4()),
            "actor_user_id": str(uuid4()),
            "device_id": "laptop-12",
            "device_is_new": False,
            "accessed_at": "2026-09-09T12:00:00",
            "after_hours": False,
        },
    ],
    ids=[
        "empty-body",
        "only-document-id",
        "missing-after-hours",
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
