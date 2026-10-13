"""HTTP-level tests for the knowledge-graph routes, ``SPEC.md`` 3.11 / FR-10.

Two tiers, mirroring the liboqs pattern in :mod:`tests.test_audit_checkpoint`:

1. Always-run tests that need no Neo4j. They cover route wiring, role
   authorization (401/403), and the error-branch HTTP status mapping
   (``GraphNotConfiguredError`` -> 503, invalid input -> 422, unknown document
   -> 404, out-of-range query -> 422). The 503 tests force Neo4j *unconfigured*
   so the mapping is exercised deterministically on the bare host and does not
   flip to 201 in a full-stack run where Neo4j happens to be reachable.
2. A gated integration test (``_requires_neo4j``) that seeds the demo graph and
   walks status -> seed -> document paths -> attack-paths against a real driver.
   It skips (never silently passes) when Neo4j is unconfigured or unreachable.
"""

from __future__ import annotations

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.api.deps import ACTOR_ROLE_HEADER
from app.api.router import API_V1_PREFIX
from app.config import get_settings
from app.db.enums import UserRole
from app.db.models import Document

GRAPH = f"{API_V1_PREFIX}/graph"
STATUS_URL = f"{GRAPH}/status"
SEED_URL = f"{GRAPH}/seed"
ATTACK_PATHS_URL = f"{GRAPH}/attack-paths"


def _paths_url(document_id: object) -> str:
    return f"{GRAPH}/documents/{document_id}/paths"


def _headers(role: UserRole) -> dict[str, str]:
    return {ACTOR_ROLE_HEADER: role.value}


# Allowed by GraphCaller: analyst, admin, ciso, engineer.
ANALYST_HEADERS = _headers(UserRole.SECURITY_ANALYST)
# Not in GraphCaller: data owner, compliance officer, auditor.
OWNER_HEADERS = _headers(UserRole.DATA_OWNER)
AUDITOR_HEADERS = _headers(UserRole.AUDITOR)


def _force_neo4j_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make ``is_graph_configured()`` return False regardless of host env."""
    for var in ("QAEGIS_NEO4J_URI", "QAEGIS_NEO4J_USER", "QAEGIS_NEO4J_PASSWORD"):
        monkeypatch.setenv(var, "")
    get_settings.cache_clear()


def _force_neo4j_set(monkeypatch: pytest.MonkeyPatch) -> None:
    """Make ``is_graph_configured()`` return True without connecting."""
    monkeypatch.setenv("QAEGIS_NEO4J_URI", "bolt://127.0.0.1:7687")
    monkeypatch.setenv("QAEGIS_NEO4J_USER", "neo4j")
    monkeypatch.setenv("QAEGIS_NEO4J_PASSWORD", "test-password")
    get_settings.cache_clear()


def _requires_neo4j() -> None:
    """Skip unless a real Neo4j is configured and reachable."""
    from app.graph.client import is_graph_configured, neo4j_driver

    if not is_graph_configured():
        pytest.skip("Neo4j is not configured (QAEGIS_NEO4J_URI unset)")
    try:
        with neo4j_driver() as driver:
            driver.verify_connectivity()
    except Exception as exc:  # noqa: BLE001 - any driver/connectivity failure skips
        pytest.skip(f"Neo4j not reachable: {exc}")


# ---------------------------------------------------------------------------
# /graph/status: liveness helper, no auth
# ---------------------------------------------------------------------------


def test_status_reports_unconfigured(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _force_neo4j_unset(monkeypatch)
    response = client.get(STATUS_URL)
    assert response.status_code == 200, response.text
    assert response.json() == {"configured": False}


def test_status_reports_configured(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    """``configured`` reflects settings; the endpoint never opens a connection."""
    _force_neo4j_set(monkeypatch)
    response = client.get(STATUS_URL)
    assert response.status_code == 200, response.text
    assert response.json() == {"configured": True}


# ---------------------------------------------------------------------------
# Authorization: 401 without auth, 403 for roles outside GraphCaller
# ---------------------------------------------------------------------------


def test_seed_requires_authentication(client: TestClient) -> None:
    response = client.post(SEED_URL, json={})
    assert response.status_code == 401, response.text


def test_seed_forbidden_for_disallowed_role(client: TestClient) -> None:
    response = client.post(SEED_URL, json={}, headers=OWNER_HEADERS)
    assert response.status_code == 403, response.text


def test_document_paths_forbidden_for_disallowed_role(
    client: TestClient, registered_document: Document
) -> None:
    response = client.get(_paths_url(registered_document.id), headers=AUDITOR_HEADERS)
    assert response.status_code == 403, response.text


def test_attack_paths_forbidden_for_disallowed_role(client: TestClient) -> None:
    response = client.get(
        ATTACK_PATHS_URL,
        params={"start_key": "emp-alice", "start_label": "Employee"},
        headers=OWNER_HEADERS,
    )
    assert response.status_code == 403, response.text


# ---------------------------------------------------------------------------
# Error-branch HTTP status mapping (no Neo4j required)
# ---------------------------------------------------------------------------


def test_seed_unconfigured_returns_503(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _force_neo4j_unset(monkeypatch)
    response = client.post(SEED_URL, json={}, headers=ANALYST_HEADERS)
    assert response.status_code == 503, response.text
    assert "not configured" in response.json()["detail"].lower()


def test_document_paths_unconfigured_returns_503(
    client: TestClient,
    registered_document: Document,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _force_neo4j_unset(monkeypatch)
    response = client.get(_paths_url(registered_document.id), headers=ANALYST_HEADERS)
    assert response.status_code == 503, response.text


def test_attack_paths_unconfigured_returns_503(
    client: TestClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    _force_neo4j_unset(monkeypatch)
    response = client.get(
        ATTACK_PATHS_URL,
        params={"start_key": "emp-alice", "start_label": "Employee"},
        headers=ANALYST_HEADERS,
    )
    assert response.status_code == 503, response.text


def test_attack_paths_invalid_start_label_returns_422(client: TestClient) -> None:
    """A bad label is rejected before any driver call (ValueError -> 422)."""
    response = client.get(
        ATTACK_PATHS_URL,
        params={"start_key": "x", "start_label": "NotALabel"},
        headers=ANALYST_HEADERS,
    )
    assert response.status_code == 422, response.text
    assert "start_label must be one of" in response.json()["detail"]


def test_seed_unknown_document_returns_404(client: TestClient) -> None:
    from uuid import uuid4

    response = client.post(
        SEED_URL, json={"document_id": str(uuid4())}, headers=ANALYST_HEADERS
    )
    assert response.status_code == 404, response.text


def test_document_paths_unknown_document_returns_404(client: TestClient) -> None:
    from uuid import uuid4

    response = client.get(_paths_url(uuid4()), headers=ANALYST_HEADERS)
    assert response.status_code == 404, response.text


def test_document_paths_rejects_out_of_range_max_hops(
    client: TestClient, registered_document: Document
) -> None:
    """FastAPI query validation (ge=1, le=6) fires before the handler body."""
    response = client.get(
        _paths_url(registered_document.id),
        params={"max_hops": 0},
        headers=ANALYST_HEADERS,
    )
    assert response.status_code == 422, response.text


def test_attack_paths_missing_required_query_returns_422(
    client: TestClient,
) -> None:
    response = client.get(ATTACK_PATHS_URL, headers=ANALYST_HEADERS)
    assert response.status_code == 422, response.text


def test_seed_rejects_unknown_body_field(client: TestClient) -> None:
    """``GraphSeedRequest`` forbids extras; a stray field is a 422, not ignored."""
    response = client.post(
        SEED_URL, json={"unexpected": "value"}, headers=ANALYST_HEADERS
    )
    assert response.status_code == 422, response.text


# ---------------------------------------------------------------------------
# Gated real-Neo4j integration: seed -> status -> paths -> attack-paths
# ---------------------------------------------------------------------------


def test_graph_end_to_end_against_real_neo4j(
    client: TestClient,
    db_session: Session,
    registered_document: Document,
) -> None:
    _requires_neo4j()

    status_response = client.get(STATUS_URL)
    assert status_response.status_code == 200, status_response.text
    assert status_response.json()["configured"] is True

    seed_response = client.post(
        SEED_URL,
        json={"document_id": str(registered_document.id)},
        headers=ANALYST_HEADERS,
    )
    assert seed_response.status_code == 201, seed_response.text
    seed_body = seed_response.json()
    # seed_demo_graph upserts a fixed topology: 5 nodes, 6 relationships.
    assert seed_body["nodes_upserted"] == 5
    assert seed_body["relationships_upserted"] == 6
    assert seed_body["demo"] is True

    paths_response = client.get(
        _paths_url(registered_document.id),
        params={"max_hops": 4},
        headers=ANALYST_HEADERS,
    )
    assert paths_response.status_code == 200, paths_response.text
    paths_body = paths_response.json()
    assert paths_body["document_id"] == str(registered_document.id)
    assert len(paths_body["paths"]) >= 1
    first = paths_body["paths"][0]
    assert first["hops"] >= 1
    assert len(first["nodes"]) == first["hops"] + 1
    assert len(first["relationships"]) == first["hops"]
    # The document node must appear on a path bound to this document id.
    keys_on_paths = {
        node["key"] for path in paths_body["paths"] for node in path["nodes"]
    }
    assert str(registered_document.id) in keys_on_paths

    attack_response = client.get(
        ATTACK_PATHS_URL,
        params={"start_key": "emp-alice", "start_label": "Employee", "max_hops": 4},
        headers=ANALYST_HEADERS,
    )
    assert attack_response.status_code == 200, attack_response.text
    attack_body = attack_response.json()
    assert attack_body["document_id"] is None
    assert len(attack_body["paths"]) >= 1
    # Every path starts at the requested Employee node.
    for path in attack_body["paths"]:
        assert path["nodes"][0]["key"] == "emp-alice"
        assert path["relationships"]
