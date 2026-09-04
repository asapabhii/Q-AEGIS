"""Migration scheduler, ``SPEC.md`` 3.10, implements ``PRD.md`` FR-9.

NOT IMPLEMENTED. Scheduled for Phase 5 (``SPEC.md`` Section 7). This package
exists so the module boundary is fixed before code is written; it contains no
logic, stubbed or otherwise.

When built: a Qiskit QAOA formulation of the prioritization problem, benchmarked
against classical baselines (greedy allocation, simulated annealing) on the
identical constraint set. Per ``PRD.md`` FR-9 and Risk R3, the baseline
comparison is part of the requirement itself, not a follow-up task. Make no
comparative claim about this module's effectiveness anywhere until that
benchmark exists and supports it.

Ranking output must include the specific constraint values used to produce it,
not just the resulting order.

Owner: Udhav (``WORK_DIVISION.md``).
"""
