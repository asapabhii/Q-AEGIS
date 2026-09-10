"""Tests for QAOA integration in migration scheduler, SPEC.md 3.10.

Per AGENTS.md: 70% coverage floor applies.

Owner: Udhav (WORK_DIVISION.md).
"""

import pytest
from uuid import uuid4

from app.classifier.labels import SensitivityLabel
from app.scheduler import (
    DocumentMigrationCandidate,
    MigrationConstraints,
    benchmark_all_methods,
    greedy_baseline,
    qaoa_prioritize,
)
from app.scheduler.qaoa_optimizer import is_qiskit_available


def _make_candidates() -> list[DocumentMigrationCandidate]:
    """Create sample document candidates for testing."""
    return [
        DocumentMigrationCandidate(
            document_id=uuid4(),
            sensitivity=SensitivityLabel.RESTRICTED,
            trust_score=0.2,
            data_size_bytes=5000,
            access_frequency=10.0,
        ),
        DocumentMigrationCandidate(
            document_id=uuid4(),
            sensitivity=SensitivityLabel.CONFIDENTIAL,
            trust_score=0.4,
            data_size_bytes=3000,
            access_frequency=5.0,
        ),
        DocumentMigrationCandidate(
            document_id=uuid4(),
            sensitivity=SensitivityLabel.RESTRICTED,
            trust_score=0.1,
            data_size_bytes=8000,
            access_frequency=15.0,
        ),
        DocumentMigrationCandidate(
            document_id=uuid4(),
            sensitivity=SensitivityLabel.PUBLIC,
            trust_score=0.8,
            data_size_bytes=1000,
            access_frequency=1.0,
        ),
        DocumentMigrationCandidate(
            document_id=uuid4(),
            sensitivity=SensitivityLabel.CONFIDENTIAL,
            trust_score=0.5,
            data_size_bytes=2000,
            access_frequency=3.0,
        ),
    ]


def _make_constraints() -> MigrationConstraints:
    """Create migration constraints."""
    return MigrationConstraints(
        budget_max_docs=3,
        budget_max_bytes=15000,
        weight_sensitivity=0.40,
        weight_trust_risk=0.35,
        weight_access_freq=0.15,
        weight_data_size=0.10,
    )


class TestQAOAIntegration:
    """Test QAOA integration in migration scheduler."""

    def test_qiskit_availability(self) -> None:
        """Check if Qiskit is available."""
        available = is_qiskit_available()
        assert isinstance(available, bool)

    def test_qaoa_trivial_case(self) -> None:
        """Test QAOA with trivial 3-document case."""
        candidates = _make_candidates()[:3]
        constraints = MigrationConstraints(budget_max_docs=2)

        result = qaoa_prioritize(candidates, constraints)

        assert result.method in ["qaoa", "qaoa_qiskit", "classical_fallback"]
        assert len(result.selected_document_ids) <= 2
        assert result.execution_time_seconds > 0

    def test_qaoa_vs_baseline_comparison(self) -> None:
        """Verify QAOA objective is close to greedy baseline."""
        candidates = _make_candidates()
        constraints = _make_constraints()

        greedy_result = greedy_baseline(candidates, constraints)
        qaoa_result = qaoa_prioritize(candidates, constraints)

        assert qaoa_result.execution_time_seconds > 0
        if greedy_result.objective_value > 0:
            ratio = qaoa_result.objective_value / greedy_result.objective_value
            assert ratio >= 0.5

    def test_benchmark_all_methods(self) -> None:
        """Test benchmark comparison includes QAOA."""
        candidates = _make_candidates()
        constraints = _make_constraints()

        benchmark = benchmark_all_methods(candidates, constraints)

        assert "results" in benchmark
        assert "greedy_baseline" in benchmark["results"]
        assert "simulated_annealing" in benchmark["results"]
        assert "qaoa" in benchmark["results"]

        qaoa_res = benchmark["results"]["qaoa"]
        assert "objective_value" in qaoa_res
        assert "execution_time_seconds" in qaoa_res

        assert "qaoa_greedy_overlap" in benchmark["comparison"]

    def test_qaoa_empty_candidates(self) -> None:
        """Test QAOA with empty candidate list."""
        constraints = _make_constraints()
        result = qaoa_prioritize([], constraints)

        assert result.selected_document_ids == []
        assert result.objective_value == 0.0

    def test_qaoa_large_budget(self) -> None:
        """Test when budget exceeds candidate count."""
        candidates = _make_candidates()
        constraints = MigrationConstraints(budget_max_docs=100)
        result = qaoa_prioritize(candidates, constraints)

        assert len(result.selected_document_ids) == len(candidates)


class TestQAOAFallback:
    """Test QAOA fallback behavior."""

    def test_qaoa_includes_metadata(self) -> None:
        """Verify QAOA result includes method metadata."""
        candidates = _make_candidates()
        constraints = MigrationConstraints(budget_max_docs=2)
        result = qaoa_prioritize(candidates, constraints)

        assert result.metadata is not None
