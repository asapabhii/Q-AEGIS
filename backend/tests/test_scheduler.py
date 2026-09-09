"""Tests for Migration Scheduler (SPEC.md 3.10, PRD.md FR-9).

Verifies QAOA and classical baselines (greedy, simulated annealing), constraint
enforcement, and benchmarking requirements.
"""

from uuid import uuid4

import pytest

from app.classifier.labels import SensitivityLabel
from app.db.enums import CryptoProfileType
from app.scheduler.prioritizer import (
    DocumentMigrationCandidate,
    MigrationConstraints,
    benchmark_all_methods,
    compute_document_utility,
    greedy_baseline,
    qaoa_prioritize,
    simulated_annealing_baseline,
)


@pytest.fixture
def sample_candidates() -> list[DocumentMigrationCandidate]:
    """Create a diverse set of document candidates for scheduler tests."""
    return [
        DocumentMigrationCandidate(
            document_id=uuid4(),
            sensitivity=SensitivityLabel.RESTRICTED,
            trust_score=0.15,  # High risk / urgent
            data_size_bytes=1024,
            access_frequency=50.0,
            current_crypto_profile=CryptoProfileType.AES256,
        ),
        DocumentMigrationCandidate(
            document_id=uuid4(),
            sensitivity=SensitivityLabel.CONFIDENTIAL,
            trust_score=0.40,
            data_size_bytes=2048,
            access_frequency=20.0,
            current_crypto_profile=CryptoProfileType.AES256,
        ),
        DocumentMigrationCandidate(
            document_id=uuid4(),
            sensitivity=SensitivityLabel.INTERNAL,
            trust_score=0.75,
            data_size_bytes=512,
            access_frequency=10.0,
            current_crypto_profile=CryptoProfileType.HYBRID,
        ),
        DocumentMigrationCandidate(
            document_id=uuid4(),
            sensitivity=SensitivityLabel.PUBLIC,
            trust_score=0.90,  # Low risk / low urgency
            data_size_bytes=4096,
            access_frequency=2.0,
            current_crypto_profile=CryptoProfileType.AES256,
        ),
    ]


def test_compute_document_utility(sample_candidates: list[DocumentMigrationCandidate]):
    constraints = MigrationConstraints(budget_max_docs=2)
    # RESTRICTED with low trust should have higher utility than PUBLIC with high trust
    u_restricted = compute_document_utility(
        sample_candidates[0], constraints, 4096, 50.0
    )
    u_public = compute_document_utility(sample_candidates[3], constraints, 4096, 50.0)

    assert u_restricted > u_public


def test_empty_candidates():
    constraints = MigrationConstraints(budget_max_docs=5)

    greedy_res = greedy_baseline([], constraints)
    sa_res = simulated_annealing_baseline([], constraints)
    qaoa_res = qaoa_prioritize([], constraints)

    assert greedy_res.selected_document_ids == []
    assert sa_res.selected_document_ids == []
    assert qaoa_res.selected_document_ids == []


def test_greedy_baseline_budget_enforcement(
    sample_candidates: list[DocumentMigrationCandidate],
):
    constraints = MigrationConstraints(budget_max_docs=2)
    res = greedy_baseline(sample_candidates, constraints)

    assert len(res.selected_document_ids) == 2
    # The first selected should be the most urgent (RESTRICTED, trust 0.15)
    assert res.selected_document_ids[0] == sample_candidates[0].document_id
    assert res.total_size_bytes > 0
    assert "weights" in res.constraint_snapshot


def test_greedy_baseline_byte_budget_enforcement(
    sample_candidates: list[DocumentMigrationCandidate],
):
    # Restrict budget by bytes: only enough for candidate 0 (1024 bytes)
    constraints = MigrationConstraints(budget_max_docs=3, budget_max_bytes=1500)
    res = greedy_baseline(sample_candidates, constraints)

    assert len(res.selected_document_ids) == 1
    assert res.selected_document_ids[0] == sample_candidates[0].document_id
    assert res.total_size_bytes <= 1500


def test_simulated_annealing_baseline(
    sample_candidates: list[DocumentMigrationCandidate],
):
    constraints = MigrationConstraints(budget_max_docs=2)
    res = simulated_annealing_baseline(sample_candidates, constraints, max_steps=200)

    assert len(res.selected_document_ids) <= 2
    assert res.objective_value > 0.0
    assert res.method == "simulated_annealing_baseline"
    assert "best_energy" in res.metadata


def test_qaoa_prioritize(sample_candidates: list[DocumentMigrationCandidate]):
    constraints = MigrationConstraints(budget_max_docs=2)
    res = qaoa_prioritize(sample_candidates, constraints)

    assert len(res.selected_document_ids) <= 2
    assert res.objective_value > 0.0
    assert res.method == "qaoa"
    assert "qubo_penalty_weight" in res.metadata
    # Most urgent document should be selected
    assert sample_candidates[0].document_id in res.selected_document_ids


def test_benchmark_all_methods_comparison(
    sample_candidates: list[DocumentMigrationCandidate],
):
    constraints = MigrationConstraints(budget_max_docs=2)
    benchmark = benchmark_all_methods(sample_candidates, constraints)

    assert benchmark["candidate_count"] == 4
    assert "greedy_baseline" in benchmark["results"]
    assert "simulated_annealing" in benchmark["results"]
    assert "qaoa" in benchmark["results"]

    comparison = benchmark["comparison"]
    assert "greedy_sa_overlap" in comparison
    assert "qaoa_greedy_overlap" in comparison
    assert "best_objective_value" in comparison
    assert comparison["best_objective_value"] > 0.0
