"""Migration ranking tests, ``SPEC.md`` 3.10 / FR-9."""

from app.scheduler.baselines import greedy_select, simulated_annealing_select
from app.scheduler.candidates import MigrationCandidate
from app.scheduler import qaoa as qaoa_mod
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
    # Qiskit is installed here, so a genuine Qiskit QAOA run is expected. The
    # numpy statevector fallback (also "qaoa*") is accepted for hosts without a
    # working Qiskit build.
    assert body["primary"]["method"] in {
        "qaoa_qiskit",
        "qaoa_numpy",
        "qaoa_numpy_approx",
    }
    assert "budget" in body["constraint_snapshot"]
    assert "baselines" in body["constraint_snapshot"]
    assert body["constraint_snapshot"]["window_days"] == 30
    assert body["schedule"]
    assert body["schedule"][0]["scheduled_upgrade_date"] is not None


def _unit_cost_cands() -> list[MigrationCandidate]:
    """Three unit-cost candidates so a budget of 1.0 admits exactly one."""
    return [
        MigrationCandidate(
            document_id=uuid4(),
            filename=name,
            score=score,
            cost=1.0,
            profile_type=CryptoProfileType.AES256,
            sensitivity_label="RESTRICTED",
            trust_score="0.20",
            risk_value="0.80",
        )
        for name, score in (("a.pdf", 0.9), ("b.pdf", 0.85), ("c.pdf", 0.1))
    ]


def test_qaoa_uses_numpy_fallback_when_qiskit_unavailable(monkeypatch) -> None:
    """With Qiskit reported absent, the exact numpy statevector QAOA runs."""
    monkeypatch.setattr(qaoa_mod, "qiskit_available", lambda: False)
    cands = _unit_cost_cands()
    budget = 1.0

    result = qaoa_select(cands, budget=budget, seed=1)

    assert result.method == "qaoa_numpy"
    assert result.total_cost <= budget + 1e-6
    assert len(result.selected_ids) >= 1
    # Unit costs + budget 1.0 mean a compliant solver cannot take every item;
    # the budget genuinely constrains the selection rather than being trivially
    # satisfied.
    assert len(result.selected_ids) < len(cands)


def test_qaoa_falls_back_to_numpy_when_qiskit_raises(monkeypatch) -> None:
    """A Qiskit build that raises is caught and the numpy path takes over."""
    monkeypatch.setattr(qaoa_mod, "qiskit_available", lambda: True)

    def _boom(*args, **kwargs):
        raise RuntimeError("qiskit build broken")

    monkeypatch.setattr(qaoa_mod, "_qiskit_qaoa_select", _boom)
    cands = _unit_cost_cands()
    budget = 1.0

    result = qaoa_select(cands, budget=budget, seed=1)

    assert result.method == "qaoa_numpy"
    assert result.total_cost <= budget + 1e-6
    assert len(result.selected_ids) >= 1
    assert len(result.selected_ids) < len(cands)
