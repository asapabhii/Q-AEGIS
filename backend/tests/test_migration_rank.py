"""Migration ranking tests, ``SPEC.md`` 3.10 / FR-9."""

from app.scheduler.baselines import greedy_select, simulated_annealing_select
from app.scheduler.candidates import MigrationCandidate
from app.scheduler.qaoa import qaoa_select
from app.db.enums import CryptoProfileType
from uuid import uuid4


def _cands() -> list[MigrationCandidate]:
    return [
        MigrationCandidate(
            document_id=uuid4(),
            filename="a.pdf",
            score=0.9,
            cost=1.0,
            profile_type=CryptoProfileType.AES256,
            sensitivity_label="RESTRICTED",
            trust_score="0.20",
            risk_value="0.80",
        ),
        MigrationCandidate(
            document_id=uuid4(),
            filename="b.pdf",
            score=0.5,
            cost=1.0,
            profile_type=CryptoProfileType.HYBRID,
            sensitivity_label="CONFIDENTIAL",
            trust_score="0.50",
            risk_value="0.40",
        ),
        MigrationCandidate(
            document_id=uuid4(),
            filename="c.pdf",
            score=0.2,
            cost=1.0,
            profile_type=CryptoProfileType.AES256,
            sensitivity_label="INTERNAL",
            trust_score="0.80",
            risk_value="0.20",
        ),
    ]


def test_baselines_and_qaoa_respect_budget() -> None:
    cands = _cands()
    budget = 1.5
    greedy = greedy_select(cands, budget=budget)
    anneal = simulated_annealing_select(cands, budget=budget, seed=1)
    qaoa = qaoa_select(cands, budget=budget, seed=1)
    for result in (greedy, anneal, qaoa):
        assert result.total_cost <= budget + 1e-6
        assert result.method
        assert len(result.selected_ids) >= 1


def test_rank_endpoint_returns_baselines(client, db_session, registered_document):
    from app.db.enums import UserRole
    from tests.factories import make_crypto_profile, make_risk_score, make_trust_score

    risk = make_risk_score(db_session, registered_document)
    trust = make_trust_score(db_session, registered_document, risk)
    make_crypto_profile(db_session, registered_document, trust)
    db_session.flush()

    response = client.post(
        "/api/v1/migration-schedule/rank",
        json={"budget": 2.0, "window_days": 30, "seed": 7},
        headers={"X-Q-AEGIS-Actor-Role": UserRole.SECURITY_ADMIN.value},
    )
    assert response.status_code == 201, response.text
    body = response.json()
    assert "baselines" in body
    assert len(body["baselines"]) == 2
    assert body["primary"]["method"].startswith("qaoa")
    assert "qiskit" not in body["primary"]["method"]
    assert "budget" in body["constraint_snapshot"]
    assert "baselines" in body["constraint_snapshot"]
    assert body["constraint_snapshot"]["window_days"] == 30
    assert body["schedule"]
    assert body["schedule"][0]["scheduled_upgrade_date"] is not None
