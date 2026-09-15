"""Tests for global exception handlers in ``app/api/errors.py``.

Verifies that errors are consistently returned as JSON with a ``detail`` field,
never as Starlette plain-text pages or debug HTML. Tests the 401, 422, 403, 404,
and 500 response shapes match the documented API contract.
"""

import pytest
from fastapi.testclient import TestClient

from app.api.deps import ACTOR_ROLE_HEADER
from app.api.router import API_V1_PREFIX
from app.db.enums import UserRole

HEALTH_URL = f"{API_V1_PREFIX}/health"


# --------------------------------------------------------------------------
# HTTPException (401, 403, 404, 500) passthrough
# --------------------------------------------------------------------------


def test_unauthorized_returns_json_not_html(client: TestClient) -> None:
    """401 responses are JSON, never HTML error pages."""
    response = client.get(HEALTH_URL)
    # Health endpoint needs no auth, so let's test a protected one
    response = client.get(f"{API_V1_PREFIX}/documents", headers={ACTOR_ROLE_HEADER: ""})
    assert response.status_code == 401
    assert response.headers["content-type"].startswith("application/json")
    payload = response.json()
    assert "detail" in payload


def test_forbidden_returns_json_not_html(client: TestClient) -> None:
    """403 responses are JSON, never HTML error pages."""
    # A user with COMPLIANCE_OFFICER role trying to access /documents
    # (which only allows SECURITY_ADMIN, SECURITY_ANALYST, AUDITOR, CISO, ENGINEER)
    response = client.get(
        f"{API_V1_PREFIX}/documents",
        headers={ACTOR_ROLE_HEADER: UserRole.COMPLIANCE_OFFICER.value},
    )
    assert response.status_code == 403
    assert response.headers["content-type"].startswith("application/json")
    payload = response.json()
    assert "detail" in payload


def test_not_found_returns_json_not_html(client: TestClient) -> None:
    """404 responses are JSON, never HTML error pages."""
    from uuid import uuid4

    response = client.get(
        f"{API_V1_PREFIX}/documents/{uuid4()}",
        headers={ACTOR_ROLE_HEADER: UserRole.SECURITY_ADMIN.value},
    )
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/json")
    payload = response.json()
    assert "detail" in payload


# --------------------------------------------------------------------------
# RequestValidationError (422) shape
# --------------------------------------------------------------------------


def test_validation_error_returns_fastapi_detail_shape(client: TestClient) -> None:
    """422 responses keep FastAPI's default detail shape that the frontend parses."""
    response = client.post(
        f"{API_V1_PREFIX}/documents",
        headers={ACTOR_ROLE_HEADER: UserRole.DATA_OWNER.value},
    )
    # Missing JSON body triggers 422
    assert response.status_code == 422
    payload = response.json()
    assert "detail" in payload
    assert isinstance(payload["detail"], list)
    # FastAPI detail items have 'loc', 'msg', 'type' fields
    if payload["detail"]:
        detail_item = payload["detail"][0]
        assert "loc" in detail_item
        assert "msg" in detail_item
        assert "type" in detail_item


# --------------------------------------------------------------------------
# Unhandled exceptions (500)
# --------------------------------------------------------------------------


def _explode_health_endpoint(
    client: TestClient, monkeypatch: pytest.MonkeyPatch, message: str
) -> None:
    """Replace the registered /health endpoint so the request raises."""

    def explode() -> None:
        raise RuntimeError(message)

    def iter_routes(routes: object) -> object:
        for route in routes:  # type: ignore[union-attr]
            if type(route).__name__ == "_IncludedRouter":
                yield from iter_routes(route.original_router.routes)
                continue
            yield route

    # Route objects store the unprefixed path ("/health"); the "/api/v1"
    # prefix is applied when the included router matches the request.
    for route in iter_routes(client.app.routes):
        if getattr(route, "path", None) == "/health":
            monkeypatch.setattr(route, "endpoint", explode)
            return
    raise AssertionError(f"No route registered for {HEALTH_URL}")


def test_unhandled_exception_returns_json_not_traceback(
    raising_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Unhandled exceptions return 500 JSON, never a traceback or debug page."""
    _explode_health_endpoint(raising_client, monkeypatch, "Something unexpected")

    response = raising_client.get(HEALTH_URL)
    assert response.status_code == 500
    assert response.headers["content-type"].startswith("application/json")
    payload = response.json()
    assert "detail" in payload
    assert payload["detail"] == "Internal server error."


def test_unhandled_exception_does_not_leak_internals(
    raising_client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """500 response body contains no stack trace or internal paths."""
    _explode_health_endpoint(
        raising_client, monkeypatch, "/internal/path/to/sensitive/code"
    )

    response = raising_client.get(HEALTH_URL)
    body = response.text
    # None of the exception details should appear in the response
    assert "internal/path" not in body
    assert "RuntimeError" not in body
    assert "Traceback" not in body


# --------------------------------------------------------------------------
# ErrorResponse model validation
# --------------------------------------------------------------------------


def test_error_response_extra_fields_are_rejected() -> None:
    """ErrorResponse forbids extra fields per model_config."""
    from app.api.errors import ErrorResponse

    # Valid usage
    resp = ErrorResponse(detail="Not found")
    assert resp.detail == "Not found"

    # Extra fields raise validation errors due to extra="forbid"
    with pytest.raises(Exception):  # Pydantic ValidationError
        ErrorResponse(detail="Bad", extra_field="rejected")


# --------------------------------------------------------------------------
# Integration: error shape consistency across endpoints
# --------------------------------------------------------------------------


def test_401_has_no_traceback_in_body(client: TestClient) -> None:
    """All 401 responses share the same sanitary shape."""
    response = client.post(f"{API_V1_PREFIX}/classify", json={})
    assert response.status_code == 401
    body = response.json()
    assert "detail" in body
    assert isinstance(body["detail"], str)


def test_422_has_detailed_validation_errors(client: TestClient) -> None:
    """422 responses include validation error details for debugging."""
    response = client.post(
        f"{API_V1_PREFIX}/classify",
        json={"document_id": "not-a-uuid", "content": "test"},
        headers={ACTOR_ROLE_HEADER: UserRole.DATA_OWNER.value},
    )
    assert response.status_code == 422
    body = response.json()
    # The detail should be a list of validation errors
    assert isinstance(body["detail"], list)
    assert len(body["detail"]) > 0
    # Each error should identify the problematic field
    locations = [d.get("loc", []) for d in body["detail"]]
    # At least one error should mention document_id or content
    assert any("document_id" in str(loc) or "content" in str(loc) for loc in locations)
