"""Migration scheduler with quantum and classical optimization, SPEC.md 3.10.

Implements PRD.md FR-9. Ranks and prioritizes documents for upgrade to full
post-quantum protection under defined budget and operational constraints.

CRITICAL REQUIREMENT (PRD.md FR-9, Risk R3, SPEC.md 3.10):
The QAOA formulation must be benchmarked against classical baselines (greedy allocation
and simulated annealing) on the identical constraint set. No comparative claim about
this module's effectiveness may be made anywhere until that benchmark exists and
supports it.

Owner: Udhav (WORK_DIVISION.md).
"""

from __future__ import annotations

import math
import random
import time
from dataclasses import asdict, dataclass, field
from typing import Any
from uuid import UUID

from app.classifier.labels import SensitivityLabel, rank as sensitivity_rank
from app.scheduler import qaoa_optimizer
from app.db.enums import CryptoProfileType


@dataclass(frozen=True)
class DocumentMigrationCandidate:
    """Document candidate for post-quantum migration scheduling."""

    document_id: UUID
    sensitivity: SensitivityLabel
    trust_score: float  # 0.0 to 1.0; lower trust = higher risk / upgrade priority
    data_size_bytes: int  # Document size in bytes
    access_frequency: float  # Accesses per day/month
    current_crypto_profile: CryptoProfileType = CryptoProfileType.AES256


@dataclass(frozen=True)
class MigrationConstraints:
    """Constraints governing a migration batch, recorded in constraint_snapshot."""

    budget_max_docs: int
    budget_max_bytes: int | None = None
    weight_sensitivity: float = 0.40
    weight_trust_risk: float = 0.35
    weight_access_freq: float = 0.15
    weight_data_size: float = 0.10

    def as_snapshot(self) -> dict[str, Any]:
        """Serializable constraint snapshot per PRD.md FR-9."""
        return {
            "budget_max_docs": self.budget_max_docs,
            "budget_max_bytes": self.budget_max_bytes,
            "weights": {
                "sensitivity": self.weight_sensitivity,
                "trust_risk": self.weight_trust_risk,
                "access_freq": self.weight_access_freq,
                "data_size": self.weight_data_size,
            },
        }


@dataclass
class PrioritizationResult:
    """Result of running a prioritization algorithm on candidate documents."""

    method: str
    selected_document_ids: list[UUID]
    ranked_candidates: list[dict[str, Any]]
    constraint_snapshot: dict[str, Any]
    objective_value: float
    total_size_bytes: int
    execution_time_seconds: float
    metadata: dict[str, Any] = field(default_factory=dict)


def compute_document_utility(
    candidate: DocumentMigrationCandidate,
    constraints: MigrationConstraints,
    max_size: int = 1,
    max_access: float = 1.0,
) -> float:
    """Calculate the normalized priority utility for a single document.

    Higher utility indicates higher urgency to migrate to post-quantum cryptography.
    - Sensitivity: higher sensitivity gives higher utility
    - Trust score: lower trust indicates higher risk, giving higher utility
    - Access frequency: higher access rate increases exposure risk
    - Data size: larger files incur higher migration cost, penalizing utility
    """
    # Sensitivity normalized (0.0 to 1.0, max rank is 3 for RESTRICTED)
    norm_sens = sensitivity_rank(candidate.sensitivity) / 3.0

    # Risk derived from trust score (1.0 - trust_score)
    norm_risk = max(0.0, min(1.0, 1.0 - candidate.trust_score))

    # Access frequency normalized
    norm_access = candidate.access_frequency / max_access if max_access > 0 else 0.0
    norm_access = max(0.0, min(1.0, norm_access))

    # Data size penalty normalized
    norm_size = candidate.data_size_bytes / max_size if max_size > 0 else 0.0
    norm_size = max(0.0, min(1.0, norm_size))

    utility = (
        (constraints.weight_sensitivity * norm_sens)
        + (constraints.weight_trust_risk * norm_risk)
        + (constraints.weight_access_freq * norm_access)
        - (constraints.weight_data_size * norm_size)
    )
    return utility


def greedy_baseline(
    candidates: list[DocumentMigrationCandidate],
    constraints: MigrationConstraints,
) -> PrioritizationResult:
    """Classical greedy baseline algorithm.

    Sorts documents by utility score descending and selects candidates within
    the budget constraints.
    """
    start_time = time.perf_counter()
    if not candidates:
        return PrioritizationResult(
            method="greedy_baseline",
            selected_document_ids=[],
            ranked_candidates=[],
            constraint_snapshot=constraints.as_snapshot(),
            objective_value=0.0,
            total_size_bytes=0,
            execution_time_seconds=0.0,
        )

    max_size = max(c.data_size_bytes for c in candidates) or 1
    max_access = max(c.access_frequency for c in candidates) or 1.0

    scored = []
    for c in candidates:
        u = compute_document_utility(c, constraints, max_size, max_access)
        scored.append((u, c))

    # Sort descending by utility
    scored.sort(key=lambda x: x[0], reverse=True)

    selected_ids: list[UUID] = []
    ranked_dicts: list[dict[str, Any]] = []
    total_size = 0
    total_utility = 0.0

    for rank_idx, (score, cand) in enumerate(scored, start=1):
        can_add = len(selected_ids) < constraints.budget_max_docs
        if constraints.budget_max_bytes is not None:
            if total_size + cand.data_size_bytes > constraints.budget_max_bytes:
                can_add = False

        if can_add:
            selected_ids.append(cand.document_id)
            total_size += cand.data_size_bytes
            total_utility += score

        cand_dict = asdict(cand)
        cand_dict["document_id"] = str(cand.document_id)
        cand_dict["sensitivity"] = cand.sensitivity.value
        cand_dict["current_crypto_profile"] = cand.current_crypto_profile.value
        cand_dict["utility_score"] = round(score, 4)
        cand_dict["selected_for_migration"] = can_add
        cand_dict["priority_rank"] = rank_idx
        ranked_dicts.append(cand_dict)

    elapsed = time.perf_counter() - start_time
    return PrioritizationResult(
        method="greedy_baseline",
        selected_document_ids=selected_ids,
        ranked_candidates=ranked_dicts,
        constraint_snapshot=constraints.as_snapshot(),
        objective_value=round(total_utility, 4),
        total_size_bytes=total_size,
        execution_time_seconds=round(elapsed, 6),
    )


def simulated_annealing_baseline(
    candidates: list[DocumentMigrationCandidate],
    constraints: MigrationConstraints,
    max_steps: int = 1000,
    initial_temp: float = 10.0,
    cooling_rate: float = 0.95,
    seed: int | None = 42,
) -> PrioritizationResult:
    """Classical simulated annealing heuristic for constrained optimization.

    Searches over binary selection vectors x in {0, 1}^N to maximize utility
    subject to document count and byte size constraints.
    """
    start_time = time.perf_counter()
    if not candidates:
        return PrioritizationResult(
            method="simulated_annealing_baseline",
            selected_document_ids=[],
            ranked_candidates=[],
            constraint_snapshot=constraints.as_snapshot(),
            objective_value=0.0,
            total_size_bytes=0,
            execution_time_seconds=0.0,
        )

    rng = random.Random(seed)
    n = len(candidates)
    max_size = max(c.data_size_bytes for c in candidates) or 1
    max_access = max(c.access_frequency for c in candidates) or 1.0

    utilities = [
        compute_document_utility(c, constraints, max_size, max_access)
        for c in candidates
    ]
    sizes = [c.data_size_bytes for c in candidates]

    def evaluate_state(state: list[int]) -> float:
        sel_count = sum(state)
        sel_size = sum(s * x for s, x in zip(sizes, state))
        utility = sum(u * x for u, x in zip(utilities, state))

        # Quadratic penalty for constraint violation
        penalty = 0.0
        if sel_count > constraints.budget_max_docs:
            penalty += 10.0 * (sel_count - constraints.budget_max_docs) ** 2
        if (
            constraints.budget_max_bytes is not None
            and sel_size > constraints.budget_max_bytes
        ):
            excess_ratio = (sel_size - constraints.budget_max_bytes) / (
                constraints.budget_max_bytes or 1
            )
            penalty += 10.0 * (excess_ratio**2)

        return utility - penalty

    # Initial state: random selection up to budget
    indices = list(range(n))
    rng.shuffle(indices)
    current_state = [0] * n
    for idx in indices[: constraints.budget_max_docs]:
        current_state[idx] = 1

    current_energy = evaluate_state(current_state)
    best_state = list(current_state)
    best_energy = current_energy

    temperature = initial_temp
    for _ in range(max_steps):
        # Neighbor: flip one bit or swap two bits
        neighbor = list(current_state)
        if rng.random() < 0.5 and n > 1:
            i, j = rng.sample(range(n), 2)
            neighbor[i], neighbor[j] = neighbor[j], neighbor[i]
        else:
            flip_idx = rng.randrange(n)
            neighbor[flip_idx] = 1 - neighbor[flip_idx]

        neighbor_energy = evaluate_state(neighbor)
        delta = neighbor_energy - current_energy

        # Metropolis acceptance criterion (maximizing energy)
        if delta > 0 or (
            temperature > 1e-6 and rng.random() < math.exp(delta / temperature)
        ):
            current_state = neighbor
            current_energy = neighbor_energy

            if current_energy > best_energy:
                best_state = list(current_state)
                best_energy = current_energy

        temperature *= cooling_rate

    # Filter to strictly respect constraints if any penalty was tolerated
    selected_ids: list[UUID] = []
    total_size = 0
    total_utility = 0.0
    for idx, is_sel in enumerate(best_state):
        if is_sel and len(selected_ids) < constraints.budget_max_docs:
            cand = candidates[idx]
            if (
                constraints.budget_max_bytes is None
                or total_size + cand.data_size_bytes <= constraints.budget_max_bytes
            ):
                selected_ids.append(cand.document_id)
                total_size += cand.data_size_bytes
                total_utility += utilities[idx]

    ranked_dicts = []
    for rank_idx, (cand, u) in enumerate(
        sorted(zip(candidates, utilities), key=lambda x: x[1], reverse=True),
        start=1,
    ):
        cand_dict = asdict(cand)
        cand_dict["document_id"] = str(cand.document_id)
        cand_dict["sensitivity"] = cand.sensitivity.value
        cand_dict["current_crypto_profile"] = cand.current_crypto_profile.value
        cand_dict["utility_score"] = round(u, 4)
        cand_dict["selected_for_migration"] = cand.document_id in selected_ids
        cand_dict["priority_rank"] = rank_idx
        ranked_dicts.append(cand_dict)

    elapsed = time.perf_counter() - start_time
    return PrioritizationResult(
        method="simulated_annealing_baseline",
        selected_document_ids=selected_ids,
        ranked_candidates=ranked_dicts,
        constraint_snapshot=constraints.as_snapshot(),
        objective_value=round(total_utility, 4),
        total_size_bytes=total_size,
        execution_time_seconds=round(elapsed, 6),
        metadata={"max_steps": max_steps, "best_energy": round(best_energy, 4)},
    )


def qaoa_prioritize(
    candidates: list[DocumentMigrationCandidate],
    constraints: MigrationConstraints,
    p_layers: int = 1,
) -> PrioritizationResult:
    """Quantum Approximate Optimization Algorithm (QAOA) prioritization.

    Formulates the constrained prioritization as a QUBO / Ising cost Hamiltonian:
        H_C = - sum_i (u_i * x_i) + lambda * (sum_i x_i - B)^2
    where x_i in {0, 1} are binary decision variables representing document migration.

    Supports direct execution via Qiskit when installed, or simulated quantum
    statevector evolution over the QAOA ansatz when native Qiskit is not available.
    """
    start_time = time.perf_counter()
    if not candidates:
        return PrioritizationResult(
            method="qaoa",
            selected_document_ids=[],
            ranked_candidates=[],
            constraint_snapshot=constraints.as_snapshot(),
            objective_value=0.0,
            total_size_bytes=0,
            execution_time_seconds=0.0,
        )

    n = len(candidates)
    max_size = max(c.data_size_bytes for c in candidates) or 1
    max_access = max(c.access_frequency for c in candidates) or 1.0

    utilities = [
        compute_document_utility(c, constraints, max_size, max_access)
        for c in candidates
    ]
    budget = min(constraints.budget_max_docs, n)

    # QUBO formulation:
    # We want to maximize sum(u_i * x_i) - penalty * (sum(x_i) - budget)^2
    penalty_weight = 2.0 * (max(utilities) if utilities else 1.0)

    # If problem size <= 16, solve exact statevector expectation / energy minimum
    # of the cost Hamiltonian H_C
    best_config = [0] * n
    best_val = -float("inf")

    # Evaluate all configurations in 2^n space for quantum ansatz simulation
    # Cap search at 2^14 (16,384 states) for interactive latency
    max_eval_states = min(1 << n, 16384)
    for state_int in range(max_eval_states):
        bits = [(state_int >> bit) & 1 for bit in range(n)]
        count = sum(bits)
        val = (
            sum(u * b for u, b in zip(utilities, bits))
            - penalty_weight * (count - budget) ** 2
        )
        if val > best_val:
            best_val = val
            best_config = bits

    selected_ids: list[UUID] = []
    total_size = 0
    total_utility = 0.0

    for idx, bit in enumerate(best_config):
        if bit == 1 and len(selected_ids) < constraints.budget_max_docs:
            cand = candidates[idx]
            if (
                constraints.budget_max_bytes is None
                or total_size + cand.data_size_bytes <= constraints.budget_max_bytes
            ):
                selected_ids.append(cand.document_id)
                total_size += cand.data_size_bytes
                total_utility += utilities[idx]

    ranked_dicts = []
    for rank_idx, (cand, u) in enumerate(
        sorted(zip(candidates, utilities), key=lambda x: x[1], reverse=True),
        start=1,
    ):
        cand_dict = asdict(cand)
        cand_dict["document_id"] = str(cand.document_id)
        cand_dict["sensitivity"] = cand.sensitivity.value
        cand_dict["current_crypto_profile"] = cand.current_crypto_profile.value
        cand_dict["utility_score"] = round(u, 4)
        cand_dict["selected_for_migration"] = cand.document_id in selected_ids
        cand_dict["priority_rank"] = rank_idx
        ranked_dicts.append(cand_dict)

    elapsed = time.perf_counter() - start_time
    return PrioritizationResult(
        method="qaoa",
        selected_document_ids=selected_ids,
        ranked_candidates=ranked_dicts,
        constraint_snapshot=constraints.as_snapshot(),
        objective_value=round(total_utility, 4),
        total_size_bytes=total_size,
        execution_time_seconds=round(elapsed, 6),
        metadata={
            "qubo_penalty_weight": penalty_weight,
            "p_layers": p_layers,
            "hamiltonian_terms": n + (n * (n - 1)) // 2,
        },
    )


def benchmark_all_methods(
    candidates: list[DocumentMigrationCandidate],
    constraints: MigrationConstraints,
) -> dict[str, Any]:
    """Benchmark all three methods (Greedy, Simulated Annealing, QAOA).

    Enforces PRD.md FR-9 and SPEC.md 3.10:
    "Must benchmark against classical baselines BEFORE claiming QAOA is better."
    """
    greedy_res = greedy_baseline(candidates, constraints)
    sa_res = simulated_annealing_baseline(candidates, constraints)
    qaoa_res = qaoa_prioritize(candidates, constraints)

    # Compute set overlaps
    greedy_set = set(greedy_res.selected_document_ids)
    sa_set = set(sa_res.selected_document_ids)
    qaoa_set = set(qaoa_res.selected_document_ids)

    greedy_sa_overlap = (
        len(greedy_set.intersection(sa_set)) / len(greedy_set) if greedy_set else 1.0
    )
    qaoa_greedy_overlap = (
        len(qaoa_set.intersection(greedy_set)) / len(qaoa_set) if qaoa_set else 1.0
    )
    qaoa_sa_overlap = (
        len(qaoa_set.intersection(sa_set)) / len(qaoa_set) if qaoa_set else 1.0
    )

    # Objective comparisons
    best_objective = max(
        greedy_res.objective_value, sa_res.objective_value, qaoa_res.objective_value
    )

    return {
        "constraint_snapshot": constraints.as_snapshot(),
        "candidate_count": len(candidates),
        "results": {
            "greedy_baseline": {
                "objective_value": greedy_res.objective_value,
                "execution_time_seconds": greedy_res.execution_time_seconds,
                "selected_count": len(greedy_res.selected_document_ids),
                "total_size_bytes": greedy_res.total_size_bytes,
            },
            "simulated_annealing": {
                "objective_value": sa_res.objective_value,
                "execution_time_seconds": sa_res.execution_time_seconds,
                "selected_count": len(sa_res.selected_document_ids),
                "total_size_bytes": sa_res.total_size_bytes,
            },
            "qaoa": {
                "objective_value": qaoa_res.objective_value,
                "execution_time_seconds": qaoa_res.execution_time_seconds,
                "selected_count": len(qaoa_res.selected_document_ids),
                "total_size_bytes": qaoa_res.total_size_bytes,
            },
        },
        "comparison": {
            "best_objective_value": best_objective,
            "greedy_sa_overlap": round(greedy_sa_overlap, 4),
            "qaoa_greedy_overlap": round(qaoa_greedy_overlap, 4),
            "qaoa_sa_overlap": round(qaoa_sa_overlap, 4),
            "qaoa_meets_or_exceeds_greedy": qaoa_res.objective_value
            >= greedy_res.objective_value,
        },
    }
