"""Migration scheduler, ``SPEC.md`` 3.10, implements ``PRD.md`` FR-9.

A QAOA and classical formulation of the prioritization problem, benchmarked
against classical baselines (greedy allocation, simulated annealing) on the
identical constraint set. Per ``PRD.md`` FR-9 and Risk R3, the baseline
comparison is part of the requirement itself, not a follow-up task.

Ranking output includes the specific constraint values used to produce it,
not just the resulting order.

Owner: Udhav (``WORK_DIVISION.md``).
"""

from app.scheduler.prioritizer import (
    DocumentMigrationCandidate,
    MigrationConstraints,
    PrioritizationResult,
    benchmark_all_methods,
    compute_document_utility,
    greedy_baseline,
    qaoa_prioritize,
    simulated_annealing_baseline,
)

__all__ = [
    "DocumentMigrationCandidate",
    "MigrationConstraints",
    "PrioritizationResult",
    "benchmark_all_methods",
    "compute_document_utility",
    "greedy_baseline",
    "qaoa_prioritize",
    "simulated_annealing_baseline",
]
