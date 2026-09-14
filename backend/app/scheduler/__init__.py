"""Migration scheduler, ``SPEC.md`` 3.10, implements ``PRD.md`` FR-9.

Ranks protected documents for full post-quantum upgrade under a budget.
Primary method is QAOA (Qiskit when available, numpy statevector otherwise).
Every ranking also runs greedy and simulated-annealing baselines on the
identical constraint set; totals are returned together so FR-9 / Risk R3 is
satisfied without a separate follow-up task.

Ranking output always includes ``constraint_snapshot`` values (budget,
candidates, baseline totals), not only the resulting order.
"""

from app.scheduler.rank import rank_and_persist
from app.scheduler.schemas import MigrationRankRequest, MigrationRankResponse

__all__ = [
    "MigrationRankRequest",
    "MigrationRankResponse",
    "rank_and_persist",
]
