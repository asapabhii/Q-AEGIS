import pytest
from app.scheduler.prioritizer import (
    DocumentCandidate,
    greedy_baseline,
    simulated_annealing_baseline,
    qaoa_prioritize,
    benchmark_all_methods,
)


def get_sample_candidates():
    return [
        DocumentCandidate(
            document_id="doc1",
            size_bytes=100,
            sensitivity_value=5,
            trust_score=0.2,
            access_frequency=10,
        ),
        DocumentCandidate(
            document_id="doc2",
            size_bytes=200,
            sensitivity_value=3,
            trust_score=0.8,
            access_frequency=5,
        ),
        DocumentCandidate(
            document_id="doc3",
            size_bytes=50,
            sensitivity_value=4,
            trust_score=0.5,
            access_frequency=2,
        ),
        DocumentCandidate(
            document_id="doc4",
            size_bytes=300,
            sensitivity_value=2,
            trust_score=0.9,
            access_frequency=1,
        ),
        DocumentCandidate(
            document_id="doc5",
            size_bytes=150,
            sensitivity_value=5,
            trust_score=0.1,
            access_frequency=20,
        ),
    ]


def test_document_candidate_value():
    doc = DocumentCandidate(
        document_id="test",
        size_bytes=100,
        sensitivity_value=5,
        trust_score=0.2,
        access_frequency=10,
    )
    # Risk multiplier = 1.0 + (1.0 - 0.2) = 1.8
    # Log access = 1 + log1p(10) ~ 3.397
    # Value = 5 * 1.8 * 3.397 ~ 30.58
    assert doc.value > 0


def test_greedy_baseline():
    candidates = get_sample_candidates()
    budget = 200
    selected = greedy_baseline(candidates, budget)
    # doc1 has highest value density, takes 100 bytes. doc5 is 150 bytes (won't fit).
    # Then doc3 is 50 bytes (fits).
    assert "doc1" in selected
    assert "doc3" in selected
    assert "doc5" not in selected


def test_simulated_annealing_baseline():
    candidates = get_sample_candidates()
    budget = 200
    selected = simulated_annealing_baseline(candidates, budget, iterations=100)
    total_size = sum(c.size_bytes for c in candidates if c.document_id in selected)
    assert total_size <= budget


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_qaoa_prioritize():
    candidates = get_sample_candidates()
    budget = 200
    selected = qaoa_prioritize(candidates, budget)
    total_size = sum(c.size_bytes for c in candidates if c.document_id in selected)
    assert total_size <= budget


def test_qaoa_fallback():
    # If more than 15 items, it should fallback to greedy
    candidates = [
        DocumentCandidate(
            document_id=f"doc{i}",
            size_bytes=10,
            sensitivity_value=1,
            trust_score=0.9,
            access_frequency=1,
        )
        for i in range(16)
    ]
    budget = 50
    selected = qaoa_prioritize(candidates, budget)
    assert len(selected) == 5  # 5 * 10 = 50


@pytest.mark.filterwarnings("ignore::DeprecationWarning")
def test_benchmark_all_methods():
    candidates = get_sample_candidates()
    budget = 200
    res = benchmark_all_methods(candidates, budget)
    assert "greedy" in res["results"]
    assert "simulated_annealing" in res["results"]
    assert "qaoa" in res["results"]
    assert res["budget_bytes"] == budget
