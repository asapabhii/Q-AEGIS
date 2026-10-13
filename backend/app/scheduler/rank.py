"""Rank documents for PQ migration and persist the schedule, ``SPEC.md`` 3.10.

Runs QAOA plus greedy and simulated-annealing baselines on the identical
candidate set and budget. Persists the primary (QAOA) ordering into
``migration_schedule`` with a full ``constraint_snapshot``. Comparative
totals are returned so FR-9's baseline requirement is met in the same call;
this module does not assert that QAOA is better.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy.orm import Session

from app.db.models import MigrationSchedule
from app.scheduler.baselines import (
    SelectionResult,
    greedy_select,
    simulated_annealing_select,
)
from app.scheduler.candidates import (
    RANKER_VERSION,
    MigrationCandidate,
    collect_candidates,
    replace_schedule,
)
from app.scheduler.qaoa import qaoa_select, qiskit_available


@dataclass(frozen=True)
class RankOutcome:
    """One ranking run: schedule rows plus baseline comparison."""

    rows: list[MigrationSchedule]
    primary: SelectionResult
    baselines: tuple[SelectionResult, ...]
    constraint_snapshot: dict[str, Any]
    candidates: tuple[MigrationCandidate, ...]


def rank_and_persist(
    session: Session,
    *,
    budget: float,
    window_days: int = 30,
    seed: int = 42,
) -> RankOutcome:
    """Collect candidates, run three methods, persist the QAOA ordering."""
    if budget <= 0:
        raise ValueError("budget must be positive")
    if window_days <= 0:
        raise ValueError("window_days must be positive")

    candidates = collect_candidates(session)
    greedy = greedy_select(candidates, budget=budget)
    annealing = simulated_annealing_select(candidates, budget=budget, seed=seed)
    primary = qaoa_select(candidates, budget=budget, seed=seed)

    constraint_snapshot: dict[str, Any] = {
        "ranker_version": RANKER_VERSION,
        "budget": budget,
        "window_days": window_days,
        "seed": seed,
        "qiskit_available": qiskit_available(),
        "primary_method": primary.method,
        "candidate_count": len(candidates),
        "candidates": [
            {
                "document_id": str(c.document_id),
                "filename": c.filename,
                "score": c.score,
                "cost": c.cost,
                "profile_type": c.profile_type.value if c.profile_type else None,
                "sensitivity_label": c.sensitivity_label,
                "trust_score": c.trust_score,
                "risk_value": c.risk_value,
            }
            for c in candidates
        ],
        "baselines": {
            greedy.method: {
                "selected_ids": list(greedy.selected_ids),
                "total_score": greedy.total_score,
                "total_cost": greedy.total_cost,
            },
            annealing.method: {
                "selected_ids": list(annealing.selected_ids),
                "total_score": annealing.total_score,
                "total_cost": annealing.total_cost,
            },
            primary.method: {
                "selected_ids": list(primary.selected_ids),
                "total_score": primary.total_score,
                "total_cost": primary.total_cost,
            },
        },
        "ranked_at": datetime.now(timezone.utc).isoformat(),
    }

    rows = replace_schedule(
        session,
        ordered=list(primary.ordered),
        constraint_snapshot=constraint_snapshot,
        window_days=window_days,
    )
    return RankOutcome(
        rows=rows,
        primary=primary,
        baselines=(greedy, annealing),
        constraint_snapshot=constraint_snapshot,
        candidates=tuple(candidates),
    )


def migration_audit_payload(
    *,
    outcome: RankOutcome,
    schedule_ids: list[UUID],
) -> dict[str, Any]:
    """Audit payload for one ranking run. JSON primitives only.

    Carries a unique ``ranking_run_id`` (and the run's ``ranked_at``) because the
    audit chain links entries by ``payload_hash`` (the SHA-256 of this payload),
    and a chain cannot contain two entries with the same hash without its
    ``prev_hash`` links becoming ambiguous. A ranking run with no eligible
    candidates produces an otherwise byte-identical payload every time (empty
    schedule, same budget/window/seed), so two such runs would collide on the
    system chain and corrupt tail-finding. The per-run id makes every entry
    distinct, mirroring how ``policy_rule_created`` is disambiguated by its rule
    id. This is a record of a distinct event, not a reproducible computation, so
    a fresh identifier and timestamp belong in it.
    """
    return {
        "ranking_run_id": str(uuid4()),
        "ranked_at": outcome.constraint_snapshot["ranked_at"],
        "schedule_ids": [str(item) for item in schedule_ids],
        "primary_method": outcome.primary.method,
        "primary_total_score": outcome.primary.total_score,
        "primary_total_cost": outcome.primary.total_cost,
        "baseline_scores": {
            item.method: item.total_score for item in outcome.baselines
        },
        "budget": outcome.constraint_snapshot["budget"],
        "window_days": outcome.constraint_snapshot["window_days"],
        "ranker_version": RANKER_VERSION,
        "candidate_count": len(outcome.candidates),
    }
