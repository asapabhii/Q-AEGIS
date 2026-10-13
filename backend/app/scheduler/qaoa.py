"""QAOA migration prioritization, ``SPEC.md`` 3.10 / ``PRD.md`` FR-9.

Formulates the budgeted upgrade selection as a QUBO and solves it with a
depth-``p`` QAOA. When Qiskit is installed the Quantum Approximate Optimization
Algorithm genuinely runs: the diagonal cost Hamiltonian is expanded exactly into
Pauli-Z terms (via a Walsh-Hadamard transform of the energy table), a
:class:`~qiskit.circuit.library.QAOAAnsatz` is built from it, its
gamma/beta angles are optimized with SciPy COBYLA against the Qiskit
statevector expectation, and the optimized circuit is sampled to pick the best
budget-feasible bitstring. When Qiskit is absent (or ``n`` exceeds the exact
statevector limit) the module falls back to an explicit statevector QAOA of the
*same* Hamiltonian so CI and hosts without a native Qiskit build still produce a
comparable ranking on the identical constraint set.

No comparative quality claim is made here — :mod:`app.scheduler.rank` records
baseline totals alongside this method for FR-9's required comparison.
"""

from __future__ import annotations

import logging
import math
import random

from app.scheduler.baselines import SelectionResult, greedy_select
from app.scheduler.candidates import MigrationCandidate

logger = logging.getLogger(__name__)

#: Largest candidate set for which the genuine Qiskit statevector QAOA runs.
#: Beyond this the 2**n statevector is impractical, so the greedy-seeded local
#: refinement (``_large_n_qaoa_approx``) takes over, exactly as in the numpy
#: path.
_QISKIT_MAX_QUBITS = 12

#: Coefficients below this magnitude are dropped from the cost Hamiltonian.
#: The one-sided overrun penalty makes the exact expansion dense, so tiny terms
#: are pruned to keep the ``PauliEvolutionGate`` synthesizable without changing
#: the selection.
_HAMILTONIAN_COEFF_FLOOR = 1e-9


def qiskit_available() -> bool:
    """Return whether ``qiskit`` imports successfully."""
    try:
        import qiskit  # noqa: F401

        return True
    except Exception:
        return False


def _bitstring_cost(
    bits: list[int],
    scores: list[float],
    costs: list[float],
    budget: float,
    penalty: float,
) -> float:
    """QUBO energy to minimize: ``-score + penalty * overrun^2``."""
    total_score = 0.0
    total_cost = 0.0
    for bit, score, cost in zip(bits, scores, costs):
        if bit:
            total_score += score
            total_cost += cost
    overrun = max(0.0, total_cost - budget)
    return -total_score + penalty * overrun * overrun


def _numpy_qaoa_select(
    candidates: list[MigrationCandidate],
    *,
    budget: float,
    seed: int,
    p: int,
) -> SelectionResult:
    """Statevector QAOA (p layers) over the knapsack QUBO, no Qiskit required."""
    n = len(candidates)
    if n == 0:
        return SelectionResult("qaoa_numpy", (), 0.0, 0.0, ())
    if n > 12:
        # Exact 2^n statevector is too large; seed from greedy then local search.
        return _large_n_qaoa_approx(candidates, budget=budget, seed=seed)

    scores = [c.score for c in candidates]
    costs = [c.cost for c in candidates]
    penalty = max(sum(scores) * 2.0, 1.0)
    dim = 1 << n

    def energy(index: int) -> float:
        bits = [(index >> i) & 1 for i in range(n)]
        return _bitstring_cost(bits, scores, costs, budget, penalty)

    energies = [energy(i) for i in range(dim)]
    rng = random.Random(seed)
    # Variational angles; small grid search is enough for n<=12 demos.
    best_probs: list[float] | None = None
    best_expected = float("inf")
    for _ in range(24):
        gammas = [rng.uniform(0, math.pi) for _ in range(p)]
        betas = [rng.uniform(0, math.pi) for _ in range(p)]
        # Start in uniform superposition.
        amps = [complex(1.0 / math.sqrt(dim), 0.0) for _ in range(dim)]
        for layer in range(p):
            gamma = gammas[layer]
            beta = betas[layer]
            # Cost unitary: phase by energy.
            amps = [
                a * complex(math.cos(gamma * e), -math.sin(gamma * e))
                for a, e in zip(amps, energies)
            ]
            # Mixer: RX(2*beta) on each qubit (exact for computational basis).
            for qubit in range(n):
                step = 1 << qubit
                cos_b = math.cos(beta)
                sin_b = math.sin(beta)
                new = amps[:]
                for base in range(dim):
                    if base & step:
                        continue
                    other = base | step
                    a0, a1 = amps[base], amps[other]
                    new[base] = cos_b * a0 - 1j * sin_b * a1
                    new[other] = cos_b * a1 - 1j * sin_b * a0
                amps = new
        probs = [abs(a) ** 2 for a in amps]
        expected = sum(pr * e for pr, e in zip(probs, energies))
        if expected < best_expected:
            best_expected = expected
            best_probs = probs

    assert best_probs is not None
    best_index = max(range(dim), key=lambda i: best_probs[i])
    bits = [(best_index >> i) & 1 for i in range(n)]
    chosen = [c for bit, c in zip(bits, candidates) if bit]
    spent = sum(c.cost for c in chosen)
    while spent > budget + 1e-9 and chosen:
        dropped = min(chosen, key=lambda c: c.score / c.cost if c.cost else c.score)
        chosen.remove(dropped)
        spent = sum(c.cost for c in chosen)
    chosen.sort(key=lambda c: c.score, reverse=True)
    return SelectionResult(
        method="qaoa_numpy",
        selected_ids=tuple(str(c.document_id) for c in chosen),
        total_score=round(sum(c.score for c in chosen), 6),
        total_cost=round(sum(c.cost for c in chosen), 6),
        ordered=tuple(chosen),
    )


def _large_n_qaoa_approx(
    candidates: list[MigrationCandidate], *, budget: float, seed: int
) -> SelectionResult:
    """For n>12, refine the greedy seed with QAOA-inspired bit flips."""
    greedy = greedy_select(candidates, budget=budget)
    result = _numpy_local_refine(list(greedy.ordered), candidates, budget, seed)
    return SelectionResult(
        method="qaoa_numpy_approx",
        selected_ids=result.selected_ids,
        total_score=result.total_score,
        total_cost=result.total_cost,
        ordered=result.ordered,
    )


def _numpy_local_refine(
    seed_chosen: list[MigrationCandidate],
    candidates: list[MigrationCandidate],
    budget: float,
    seed: int,
) -> SelectionResult:
    rng = random.Random(seed)
    selected = {c.document_id for c in seed_chosen}
    mask = [c.document_id in selected for c in candidates]
    scores = [c.score for c in candidates]
    costs = [c.cost for c in candidates]
    penalty = max(sum(scores) * 2.0, 1.0)

    def obj(m: list[bool]) -> float:
        bits = [1 if flag else 0 for flag in m]
        return -_bitstring_cost(bits, scores, costs, budget, penalty)

    best = mask[:]
    best_v = obj(best)
    current = mask[:]
    current_v = best_v
    for _ in range(600):
        i = rng.randrange(len(candidates))
        trial = current[:]
        trial[i] = not trial[i]
        trial_v = obj(trial)
        if trial_v >= current_v or rng.random() < 0.05:
            current = trial
            current_v = trial_v
            if current_v > best_v:
                best = current[:]
                best_v = current_v
    chosen = [c for flag, c in zip(best, candidates) if flag]
    spent = sum(c.cost for c in chosen)
    while spent > budget + 1e-9 and chosen:
        dropped = min(chosen, key=lambda c: c.score)
        chosen.remove(dropped)
        spent = sum(c.cost for c in chosen)
    chosen.sort(key=lambda c: c.score, reverse=True)
    return SelectionResult(
        method="qaoa_numpy_approx",
        selected_ids=tuple(str(c.document_id) for c in chosen),
        total_score=round(sum(c.score for c in chosen), 6),
        total_cost=round(sum(c.cost for c in chosen), 6),
        ordered=tuple(chosen),
    )


def _diagonal_cost_hamiltonian(energies: list[float], n: int):
    """Exact cost Hamiltonian for the diagonal QUBO as a ``SparsePauliOp``.

    A cost that depends only on *which* items are selected is diagonal in the
    computational basis, so it expands exactly in tensor products of ``I`` and
    ``Z``::

        E(x) = sum_S c_S * prod_{i in S} (-1)^{x_i}

    The coefficients ``c_S`` are the Walsh-Hadamard transform of the energy
    table divided by ``2**n`` (``prod_{i in S} Z_i`` has eigenvalue
    ``(-1)^{popcount(x & S)}`` on basis state ``x``). Computed with an in-place
    fast Walsh-Hadamard transform in ``O(n * 2**n)`` rather than the naive
    ``O(4**n)`` double sum.
    """
    from qiskit.quantum_info import SparsePauliOp

    dim = 1 << n
    coeffs = list(energies)
    step = 1
    while step < dim:
        for start in range(0, dim, step * 2):
            for j in range(start, start + step):
                a = coeffs[j]
                b = coeffs[j + step]
                coeffs[j] = a + b
                coeffs[j + step] = a - b
        step *= 2

    norm = float(dim)
    labels: list[str] = []
    values: list[float] = []
    for mask in range(dim):
        coeff = coeffs[mask] / norm
        if abs(coeff) <= _HAMILTONIAN_COEFF_FLOOR:
            continue
        label = ["I"] * n
        for qubit in range(n):
            if (mask >> qubit) & 1:
                # Qiskit labels are big-endian: qubit i is at position n-1-i.
                label[n - 1 - qubit] = "Z"
        labels.append("".join(label))
        values.append(coeff)

    if not labels:
        # Constant-zero Hamiltonian (all items free / no candidates): a valid
        # identity operator so QAOAAnsatz still builds.
        labels.append("I" * n)
        values.append(0.0)
    return SparsePauliOp(labels, values)


def _qaoa_restart_count(n: int) -> int:
    """More random restarts for small landscapes, fewer as the sim gets heavy."""
    if n <= 6:
        return 8
    return 3


def _qiskit_qaoa_select(
    candidates: list[MigrationCandidate],
    *,
    budget: float,
    seed: int,
    p: int,
) -> SelectionResult:
    """Genuine Qiskit QAOA over the knapsack QUBO.

    Builds the exact diagonal cost Hamiltonian, constructs a ``QAOAAnsatz`` from
    it, optimizes the gamma/beta angles with SciPy COBYLA against the Qiskit
    statevector expectation, then samples the optimized circuit and returns the
    lowest-energy budget-feasible bitstring the distribution supports. Reports
    method ``"qaoa_qiskit"``. Raises on any Qiskit/SciPy failure so the caller
    can fall back to the numpy statevector path.
    """
    import numpy as np
    from qiskit.circuit.library import QAOAAnsatz
    from qiskit.quantum_info import Statevector
    from scipy.optimize import minimize

    n = len(candidates)
    if n == 0:
        return SelectionResult("qaoa_qiskit", (), 0.0, 0.0, ())
    if n > _QISKIT_MAX_QUBITS:
        # Same large-n escape as the numpy path: an exact 2**n statevector is
        # impractical, so refine a greedy seed. Reported as an approximation,
        # never as a genuine Qiskit run.
        return _large_n_qaoa_approx(candidates, budget=budget, seed=seed)

    scores = [c.score for c in candidates]
    costs = [c.cost for c in candidates]
    penalty = max(sum(scores) * 2.0, 1.0)
    dim = 1 << n
    energies = [
        _bitstring_cost(
            [(index >> i) & 1 for i in range(n)], scores, costs, budget, penalty
        )
        for index in range(dim)
    ]
    energy_arr = np.asarray(energies, dtype=float)

    cost_op = _diagonal_cost_hamiltonian(energies, n)
    ansatz = QAOAAnsatz(cost_op, reps=p)
    num_params = ansatz.num_parameters

    def expectation(params: "np.ndarray") -> float:
        # <psi|H|psi> for a diagonal H equals sum_x P(x) E(x); evaluating it from
        # the Qiskit-simulated amplitudes is exact and far cheaper than a dense
        # operator contraction. The quantum part (cost + mixer evolution) is
        # genuinely simulated by Qiskit below.
        bound = ansatz.assign_parameters(params)
        probs = np.abs(np.asarray(Statevector(bound).data)) ** 2
        return float(np.dot(probs, energy_arr))

    rng = random.Random(seed)
    best_params: "np.ndarray | None" = None
    best_value = float("inf")
    for _ in range(_qaoa_restart_count(n)):
        x0 = np.array([rng.uniform(0.0, math.pi) for _ in range(num_params)])
        result = minimize(expectation, x0, method="COBYLA", options={"maxiter": 150})
        if result.fun < best_value:
            best_value = float(result.fun)
            best_params = np.asarray(result.x)

    assert best_params is not None
    final_probs = (
        np.abs(np.asarray(Statevector(ansatz.assign_parameters(best_params)).data)) ** 2
    )

    # Consider only basis states QAOA actually amplified, and among those pick
    # the lowest-energy set that fits the budget — the standard "best measured"
    # QAOA read-out, made robust against a high-probability infeasible state.
    ranked = np.argsort(final_probs)[::-1]
    prob_floor = float(final_probs[ranked[0]]) * 1e-3
    best_index: int | None = None
    best_energy = float("inf")
    for raw in ranked:
        index = int(raw)
        if final_probs[index] < prob_floor:
            break
        bits = [(index >> i) & 1 for i in range(n)]
        spent = sum(cost for bit, cost in zip(bits, costs) if bit)
        if spent <= budget + 1e-9 and energies[index] < best_energy:
            best_energy = energies[index]
            best_index = index

    if best_index is None:
        best_index = int(ranked[0])  # repaired below

    bits = [(best_index >> i) & 1 for i in range(n)]
    chosen = [c for bit, c in zip(bits, candidates) if bit]
    spent = sum(c.cost for c in chosen)
    while spent > budget + 1e-9 and chosen:
        dropped = min(chosen, key=lambda c: c.score / c.cost if c.cost else c.score)
        chosen.remove(dropped)
        spent = sum(c.cost for c in chosen)
    chosen.sort(key=lambda c: c.score, reverse=True)
    return SelectionResult(
        method="qaoa_qiskit",
        selected_ids=tuple(str(c.document_id) for c in chosen),
        total_score=round(sum(c.score for c in chosen), 6),
        total_cost=round(sum(c.cost for c in chosen), 6),
        ordered=tuple(chosen),
    )


def qaoa_select(
    candidates: list[MigrationCandidate],
    *,
    budget: float,
    seed: int = 42,
    p: int = 1,
) -> SelectionResult:
    """Select a budgeted subset via QAOA (Qiskit when available)."""
    if qiskit_available():
        try:
            return _qiskit_qaoa_select(candidates, budget=budget, seed=seed, p=p)
        except Exception:
            # Genuine Qiskit/SciPy failures must not be invisible: log them, then
            # fall back to the numpy statevector path over the same Hamiltonian.
            logger.warning(
                "Qiskit QAOA failed; falling back to the numpy statevector path",
                exc_info=True,
            )
            return _numpy_qaoa_select(candidates, budget=budget, seed=seed, p=p)
    return _numpy_qaoa_select(candidates, budget=budget, seed=seed, p=p)
