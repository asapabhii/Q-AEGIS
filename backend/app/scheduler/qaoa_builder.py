"""QAOA Hamiltonian builder for migration prioritization, SPEC.md 3.10.

Maps document utility scores and budget constraints to a quantum cost Hamiltonian
for QAOA optimization. Uses Qiskit's Pauli string representation for efficient
quantum circuit construction.

SECURITY NOTE: This module uses the Aer simulator, not real quantum hardware.
No claims about quantum advantage are made without benchmark evidence per
PRD FR-9 and SPEC.md 3.10.

Owner: Udhav (WORK_DIVISION.md).
"""

from __future__ import annotations

import numpy as np


def build_cost_hamiltonian(
    utilities: list[float],
    budget: int,
    penalty_weight: float | None = None,
) -> tuple[np.ndarray, float]:
    """Build QUBO matrix for migration prioritization.

    The optimization problem: maximize sum(u_i * x_i) subject to sum(x_i) = budget
    This is converted to a minimization QUBO by negating utilities and adding
    a quadratic penalty for constraint violation.

    Args:
        utilities: List of utility scores for each document (higher = more valuable)
        budget: Maximum number of documents to select
        penalty_weight: Coefficient for penalty term. Defaults to 2 * max(utilities)

    Returns:
        Tuple of (Q_matrix, offset) where objective = x^T Q x + offset
        Q_matrix is (n x n) symmetric matrix
    """
    n = len(utilities)
    if n == 0:
        return np.zeros((1, 1)), 0.0

    if penalty_weight is None:
        penalty_weight = 2.0 * max(abs(u) for u in utilities) if utilities else 1.0

    # QUBO matrix construction
    # Linear terms: -u_i (negative because we're minimizing)
    # Quadratic terms: penalty * (1 if i==j, -2 if i!=j) for constraint
    Q = np.zeros((n, n))

    # Linear contribution from utilities (we maximize, so negate for minimize)
    for i in range(n):
        Q[i, i] = -utilities[i]

    # Quadratic penalty for budget constraint: penalty * (sum(x) - budget)^2
    # = penalty * (sum(x_i)^2 - 2*budget*sum(x_i) + budget^2)
    # Expanding: penalty * (sum_i x_i^2 + sum_{i!=j} x_i*x_j - 2*budget*sum_i x_i + budget^2)
    # Since x_i^2 = x_i for binary variables:
    # = penalty * (sum_i (1 - 2*budget) * x_i + sum_{i!=j} x_i*x_j + budget^2)

    # Diagonal terms from constraint
    for i in range(n):
        Q[i, i] += penalty_weight * (1 - 2 * budget)

    # Off-diagonal terms (i != j): each pair gets penalty * 2
    for i in range(n):
        for j in range(i + 1, n):
            Q[i, j] += 2 * penalty_weight
            Q[j, i] += 2 * penalty_weight

    # Constant offset (doesn't affect optimization, but included for completeness)
    offset = penalty_weight * (budget ** 2)

    return Q, offset


def build_cost_hamiltonian_sparse(
    utilities: list[float],
    budget: int,
    penalty_weight: float | None = None,
) -> "SparsePauliOp":
    """Build cost Hamiltonian as Qiskit SparsePauliOp for quantum circuit.

    This converts the QUBO to a diagonal Hamiltonian where the ground state
    corresponds to the optimal solution. Uses Z operators because:
    Z|0> = +1, Z|1> = -1, and we map x_i = (1 - Z_i) / 2

    Args:
        utilities: List of utility scores
        budget: Maximum documents to select
        penalty_weight: Penalty coefficient

    Returns:
        SparsePauliOp representing the cost Hamiltonian
    """
    try:
        from qiskit.quantum_info import SparsePauliOp
    except ImportError:
        raise ImportError("qiskit is required for this function")

    n = len(utilities)
    if n == 0:
        return SparsePauliOp.from_list([("I" * n, 0.0)])

    if penalty_weight is None:
        penalty_weight = 2.0 * max(abs(u) for u in utilities) if utilities else 1.0

    # Build Pauli string coefficients
    # H = sum_i h_i * Z_i + sum_{i<j} h_ij * Z_i Z_j + constant
    pauli_terms: list[tuple[str, float]] = []

    # Z_i terms (linear)
    for i in range(n):
        coeff = -utilities[i] + penalty_weight * (1 - 2 * budget)
        if abs(coeff) > 1e-10:
            pauli_terms.append((make_pauli_z(n, i), coeff))

    # Z_i Z_j terms (quadratic)
    for i in range(n):
        for j in range(i + 1, n):
            coeff = penalty_weight * 2
            if abs(coeff) > 1e-10:
                pauli_terms.append((make_pauli_zz(n, i, j), coeff))

    # Constant term
    constant = penalty_weight * (budget ** 2)
    pauli_terms.append(("I" * n, constant))

    return SparsePauliOp.from_list(pauli_terms)


def build_mixer_hamiltonian(n_qubits: int) -> "SparsePauliOp":
    """Build standard QAOA mixer Hamiltonian.

    The mixer is H_M = sum_i X_i, which creates superposition and allows
    the algorithm to explore the solution space.

    Args:
        n_qubits: Number of qubits (documents)

    Returns:
        SparsePauliOp representing the mixer Hamiltonian
    """
    try:
        from qiskit.quantum_info import SparsePauliOp
    except ImportError:
        raise ImportError("qiskit is required for this function")

    if n_qubits == 0:
        return SparsePauliOp.from_list([("I", 0.0)])

    # X operator on each qubit
    pauli_terms = []
    for i in range(n_qubits):
        pauli_terms.append((make_pauli_x(n_qubits, i), 1.0))

    return SparsePauliOp.from_list(pauli_terms)


def make_pauli_z(n: int, idx: int) -> str:
    """Create Pauli Z string with Z on given index, I elsewhere."""
    return "".join("Z" if i == idx else "I" for i in range(n))


def make_pauli_x(n: int, idx: int) -> str:
    """Create Pauli X string with X on given index, I elsewhere."""
    return "".join("X" if i == idx else "I" for i in range(n))


def make_pauli_zz(n: int, i: int, j: int) -> str:
    """Create Pauli Z string with Z on indices i and j, I elsewhere."""
    return "".join("Z" if idx in (i, j) else "I" for idx in range(n))


def bitstring_to_selection(bitstring: str, budget: int) -> list[int]:
    """Convert QAOA bitstring to document selection indices.

    Args:
        bitstring: Binary string from QAOA (e.g., "01101")
        budget: Maximum number of selections allowed

    Returns:
        List of indices where bitstring[i] == '1', capped at budget
    """
    selected = []
    for i, bit in enumerate(bitstring):
        if bit == "1" and len(selected) < budget:
            selected.append(i)
    return selected


def qubo_to_selection(
    Q: np.ndarray,
    budget: int,
    utilities: list[float],
) -> list[int]:
    """Greedy fallback: select top documents by utility if QAOA unavailable.

    Args:
        Q: QUBO matrix
        budget: Maximum selections
        utilities: Original utility scores

    Returns:
        Indices of selected documents
    """
    if not utilities:
        return []

    # Sort by utility descending
    indexed = list(enumerate(utilities))
    indexed.sort(key=lambda x: x[1], reverse=True)

    # Take top budget
    return [idx for idx, _ in indexed[:budget]]