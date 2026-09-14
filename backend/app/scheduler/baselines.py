"""Classical baselines for migration prioritization, ``SPEC.md`` 3.10.

Greedy density and simulated annealing share the same candidate scores, costs,
and budget as the QAOA path so FR-9's comparison is on an identical constraint
set.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

from app.scheduler.candidates import MigrationCandidate


@dataclass(frozen=True)
class SelectionResult:
    """One method's selected set under the shared budget."""

    method: str
    selected_ids: tuple[str, ...]
    total_score: float
    total_cost: float
    ordered: tuple[MigrationCandidate, ...]


def greedy_select(
    candidates: list[MigrationCandidate], *, budget: float
) -> SelectionResult:
    """Pick by descending score/cost density until the budget is exhausted."""
    ranked = sorted(
        candidates,
        key=lambda c: (c.score / c.cost if c.cost > 0 else c.score, c.score),
        reverse=True,
    )
    chosen: list[MigrationCandidate] = []
    spent = 0.0
    for item in ranked:
        if spent + item.cost <= budget + 1e-9:
            chosen.append(item)
            spent += item.cost
    return SelectionResult(
        method="greedy",
        selected_ids=tuple(str(c.document_id) for c in chosen),
        total_score=round(sum(c.score for c in chosen), 6),
        total_cost=round(spent, 6),
        ordered=tuple(chosen),
    )


def _objective(
    mask: list[bool], candidates: list[MigrationCandidate], budget: float
) -> float:
    score = 0.0
    cost = 0.0
    for flag, item in zip(mask, candidates):
        if flag:
            score += item.score
            cost += item.cost
    if cost > budget + 1e-9:
        return score - 10.0 * (cost - budget)
    return score


def simulated_annealing_select(
    candidates: list[MigrationCandidate],
    *,
    budget: float,
    seed: int = 42,
    steps: int = 400,
) -> SelectionResult:
    """Stochastic search over subsets under the same budget as greedy/QAOA."""
    if not candidates:
        return SelectionResult("simulated_annealing", (), 0.0, 0.0, ())

    rng = random.Random(seed)
    n = len(candidates)
    current = [False] * n
    # Seed with greedy for a strong start.
    greedy = greedy_select(candidates, budget=budget)
    id_set = set(greedy.selected_ids)
    for i, item in enumerate(candidates):
        current[i] = str(item.document_id) in id_set
    current_score = _objective(current, candidates, budget)
    best = current[:]
    best_score = current_score

    temperature = 1.0
    for step in range(steps):
        i = rng.randrange(n)
        trial = current[:]
        trial[i] = not trial[i]
        trial_score = _objective(trial, candidates, budget)
        delta = trial_score - current_score
        if delta >= 0 or rng.random() < math.exp(delta / max(temperature, 1e-6)):
            current = trial
            current_score = trial_score
            if current_score > best_score:
                best = current[:]
                best_score = current_score
        temperature *= 0.995

    chosen = [c for flag, c in zip(best, candidates) if flag]
    chosen.sort(key=lambda c: c.score, reverse=True)
    spent = sum(c.cost for c in chosen)
    # Repair if annealing drifted over budget.
    while spent > budget + 1e-9 and chosen:
        dropped = chosen.pop()
        spent -= dropped.cost
    return SelectionResult(
        method="simulated_annealing",
        selected_ids=tuple(str(c.document_id) for c in chosen),
        total_score=round(sum(c.score for c in chosen), 6),
        total_cost=round(spent, 6),
        ordered=tuple(chosen),
    )
