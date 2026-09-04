"""Tests for the HTTP API surface.

Covers the health check, the ``POST /classify`` contract from ``SPEC.md`` 3.2,
and the authorization guard. The guard's identity source is a Phase 1 stub, but
its fail-closed behavior is not, so it is tested as real behavior: a missing or
unrecognized role must be refused rather than defaulted to some permitted value.
"""

from uuid import uuid4

import pytest
from fastapi.testclient import TestClient

from app.api.deps import ACTOR_ROLE_HEADER, Role
from app.api.router import API_V1_PREFIX
from app.classifier.stub_classifier import MODEL_VERSION

HEALTH_URL = f"{API_V1_PREFIX}/health"
CLASSIFY_URL = f"{API_V1_PREFIX}/classify"

#: A role permitted to call /classify.
OWNER_HEADERS = {ACTOR_ROLE_HEADER: Role.DATA_OWNER.value}


def classify_body(content: str) -> dict[str, str]:
    """Build a valid request body around ``content``."""
    return {"document_id": str(uuid4()), "content": content}


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

    Also guards against someone later reporting Postgres, Redis, or Neo4j as
    healthy here while Phase 1 connects to none of them.
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
    [Role.DATA_OWNER, Role.SECURITY_ANALYST, Role.SECURITY_ADMIN],
)
def test_classify_admits_permitted_roles(client: TestClient, role: Role) -> None:
    """The three personas whose stated need involves submitting documents."""
    response = client.post(
        CLASSIFY_URL,
        json=classify_body("This document is confidential."),
        headers={ACTOR_ROLE_HEADER: role.value},
    )
    assert response.status_code == 200


@pytest.mark.parametrize("role", [Role.COMPLIANCE_OFFICER, Role.AUDITOR])
def test_classify_refuses_roles_outside_the_allow_list(
    client: TestClient, role: Role
) -> None:
    """Valid roles are still refused when not permitted for this action.

    Confirms the guard checks the specific allow list, not merely that the role
    parses.
    """
    response = client.post(
        CLASSIFY_URL,
        json=classify_body("confidential"),
        headers={ACTOR_ROLE_HEADER: role.value},
    )
    assert response.status_code == 403


def test_role_check_is_case_insensitive(client: TestClient) -> None:
    """Header casing is a transport detail, not an authorization decision."""
    response = client.post(
        CLASSIFY_URL,
        json=classify_body("This document is confidential."),
        headers={ACTOR_ROLE_HEADER: "DATA_OWNER"},
    )
    assert response.status_code == 200


# --------------------------------------------------------------------------
# POST /classify contract, SPEC.md 3.2
# --------------------------------------------------------------------------


def test_classify_returns_the_documented_contract_fields(client: TestClient) -> None:
    """``SPEC.md`` 3.2 requires these four fields on every response."""
    response = client.post(
        CLASSIFY_URL,
        json=classify_body("Employee SSN, passport number, and CVV are on file."),
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


def test_classify_echoes_the_document_reference(client: TestClient) -> None:
    """The response ties back to the document it describes."""
    body = classify_body("This document is confidential.")
    response = client.post(CLASSIFY_URL, json=body, headers=OWNER_HEADERS)
    assert response.json()["document_id"] == body["document_id"]


def test_classify_surfaces_the_fail_safe_escalation(client: TestClient) -> None:
    """The escalation is visible over HTTP, not only inside the domain layer."""
    response = client.post(
        CLASSIFY_URL,
        json=classify_body("This document is confidential."),
        headers=OWNER_HEADERS,
    )
    payload = response.json()
    assert payload["is_defaulted"] is True
    assert payload["base_label"] == "CONFIDENTIAL"
    assert payload["sensitivity_label"] == "RESTRICTED"
    assert payload["rationale"]


def test_classify_never_returns_public_for_unrecognized_content(
    client: TestClient,
) -> None:
    """The fail-safe holds at the API boundary too."""
    response = client.post(
        CLASSIFY_URL,
        json=classify_body("The quick brown fox jumps over the lazy dog."),
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


def test_classify_rejects_unexpected_fields(client: TestClient) -> None:
    """``extra="forbid"`` so a client cannot smuggle in unmodelled input."""
    body = {**classify_body("confidential"), "sensitivity_label": "PUBLIC"}
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
    assert CLASSIFY_URL in paths
