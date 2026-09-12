"""Migration scheduler prioritizer, SPEC.md 3.10, implements PRD.md FR-9.

Ranks documents for post-quantum cryptographic upgrade given a byte budget.
Implements greedy, simulated annealing, and a QAOA (quantum) formulation.
"""

import math
import random
from typing import List, Dict, Any
from pydantic import BaseModel
import warnings

warnings.filterwarnings("ignore", category=DeprecationWarning)

# Suppress qiskit deprecation warnings for cleaner test output
with warnings.catch_warnings():
    warnings.simplefilter("ignore")
    from qiskit_algorithms.minimum_eigensolvers import QAOA
    from qiskit_algorithms.optimizers import COBYLA
    from qiskit.primitives import Sampler
    from qiskit_optimization import QuadraticProgram
    from qiskit_optimization.algorithms import MinimumEigenOptimizer


class DocumentCandidate(BaseModel):
    document_id: str
    size_bytes: int
    sensitivity_value: int  # 1 to 5
    trust_score: float  # 0.0 to 1.0 (lower is worse/higher risk)
    access_frequency: int  # accesses per month

    @property
    def value(self) -> float:
        """Compute the heuristic value of upgrading this document.

        High sensitivity, low trust (high risk), and high access frequency
        increase the priority of migration.
        """
        # Invert trust score so lower trust = higher value multiplier
        risk_multiplier = 1.0 + (1.0 - self.trust_score)
        return (
            self.sensitivity_value
            * risk_multiplier
            * (1 + math.log1p(self.access_frequency))
        )


def greedy_baseline(
    candidates: List[DocumentCandidate], budget_bytes: int
) -> List[str]:
    """Classical greedy knapsack approximation."""
    # Sort by value density (value / size) descending
    sorted_candidates = sorted(
        candidates,
        key=lambda c: c.value / max(c.size_bytes, 1),
        reverse=True,
    )

    selected = []
    current_weight = 0

    for doc in sorted_candidates:
        if current_weight + doc.size_bytes <= budget_bytes:
            selected.append(doc.document_id)
            current_weight += doc.size_bytes

    return selected


def simulated_annealing_baseline(
    candidates: List[DocumentCandidate],
    budget_bytes: int,
    initial_temp: float = 1000.0,
    cooling_rate: float = 0.95,
    iterations: int = 1000,
) -> List[str]:
    """Classical simulated annealing heuristic for the knapsack problem."""
    n = len(candidates)
    if n == 0:
        return []

    current_state = [False] * n
    current_weight = 0
    current_value = 0.0

    # Greedily initialize to a valid state
    for i, c in enumerate(candidates):
        if current_weight + c.size_bytes <= budget_bytes:
            current_state[i] = True
            current_weight += c.size_bytes
            current_value += c.value

    best_state = list(current_state)
    best_value = current_value

    temp = initial_temp

    for _ in range(iterations):
        # Pick a random document to toggle
        idx = random.randint(0, n - 1)

        new_state = list(current_state)
        new_state[idx] = not new_state[idx]

        new_weight = current_weight
        new_value = current_value

        if new_state[idx]:
            new_weight += candidates[idx].size_bytes
            new_value += candidates[idx].value
        else:
            new_weight -= candidates[idx].size_bytes
            new_value -= candidates[idx].value

        # Check constraints
        if new_weight <= budget_bytes:
            # Acceptance probability
            if new_value > current_value:
                accept = True
            else:
                delta = new_value - current_value
                # Avoid math domain error if temp is extremely close to 0
                accept = random.random() < math.exp(delta / max(temp, 1e-5))

            if accept:
                current_state = new_state
                current_weight = new_weight
                current_value = new_value

                if current_value > best_value:
                    best_state = list(current_state)
                    best_value = current_value

        temp *= cooling_rate

    return [candidates[i].document_id for i in range(n) if best_state[i]]


def qaoa_prioritize(
    candidates: List[DocumentCandidate], budget_bytes: int
) -> List[str]:
    """Quantum Approximate Optimization Algorithm (QAOA) formulation.

    Uses Qiskit to formulate the knapsack problem as a Quadratic Program,
    translates it to an Ising Hamiltonian, and solves it using a statevector
    QAOA simulation in-process.
    """
    n = len(candidates)
    if n == 0:
        return []

    # If the problem is too large, fallback to greedy
    # to avoid hanging the local simulation.
    # QAOA statevector simulation scales exponentially (2^N).
    if n > 15:
        # For a real quantum backend, this wouldn't be an issue.
        # But this is an in-process local simulator.
        return greedy_baseline(candidates, budget_bytes)

    qp = QuadraticProgram()

    # Add binary variables for each document
    for i in range(n):
        qp.binary_var(name=f"x_{i}")

    # Objective: maximize value
    linear_objective = {f"x_{i}": c.value for i, c in enumerate(candidates)}
    qp.maximize(linear=linear_objective)

    # Constraint: sum of sizes <= budget
    linear_constraint = {f"x_{i}": c.size_bytes for i, c in enumerate(candidates)}
    qp.linear_constraint(
        linear=linear_constraint, sense="<=", rhs=budget_bytes, name="budget"
    )

    # Solve using QAOA
    sampler = Sampler()
    optimizer = COBYLA(maxiter=50)
    qaoa = QAOA(sampler=sampler, optimizer=optimizer, reps=1)

    optimizer_alg = MinimumEigenOptimizer(qaoa)
    result = optimizer_alg.solve(qp)

    # Parse the result string array
    selected = []
    for i, val in enumerate(result.x):
        if val > 0.5:
            selected.append(candidates[i].document_id)

    # Verify budget constraint (QAOA penalty terms might violate hard constraints
    # if uncalibrated)
    total_size = sum(c.size_bytes for c in candidates if c.document_id in selected)
    if total_size > budget_bytes:
        # If quantum solver violates hard constraints, fallback to greedy
        return greedy_baseline(candidates, budget_bytes)

    return selected


def benchmark_all_methods(
    candidates: List[DocumentCandidate], budget_bytes: int
) -> Dict[str, Any]:
    """Run and compare all three methods on the same constraint set."""

    greedy_res = greedy_baseline(candidates, budget_bytes)
    sa_res = simulated_annealing_baseline(candidates, budget_bytes)
    qaoa_res = qaoa_prioritize(candidates, budget_bytes)

    def score(selected_ids: List[str]) -> float:
        return sum(c.value for c in candidates if c.document_id in selected_ids)

    return {
        "budget_bytes": budget_bytes,
        "results": {
            "greedy": {"selected": greedy_res, "value": score(greedy_res)},
            "simulated_annealing": {"selected": sa_res, "value": score(sa_res)},
            "qaoa": {"selected": qaoa_res, "value": score(qaoa_res)},
        },
    }
