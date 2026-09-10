# Migration Scheduler (SPEC.md 3.10)

> Owner: Udhav | Implements PRD FR-9

## Overview

The Migration Scheduler ranks and prioritizes documents for upgrade to full post-quantum protection under defined budget and operational constraints. It uses quantum optimization (QAOA) alongside classical baselines for comparison.

## Methods

### 1. Greedy Baseline (`greedy_baseline`)
Simple greedy algorithm that sorts documents by utility score and selects the top candidates within budget constraints.

**Algorithm:**
- Compute utility score for each document
- Sort by utility descending
- Select top N documents within budget

### 2. Simulated Annealing (`simulated_annealing_baseline`)
Classical heuristic optimization that escapes local minima through probabilistic acceptance of worse solutions.

**Parameters:**
- `max_steps`: 1000 (default)
- `initial_temp`: 10.0
- `cooling_rate`: 0.95

### 3. QAOA (`qaoa_prioritize`)
Quantum Approximate Optimization Algorithm using Qiskit for quantum-inspired optimization.

**Requirements:**
- Qiskit 1.2.2+
- Qiskit Aer 0.15.1+

**SECURITY NOTE:** Uses Aer simulator (not real quantum hardware). Per SPEC.md 3.10: "No comparative claim about this module's effectiveness is made anywhere until that benchmark exists and shows it."

## Utility Score Calculation

```
utility = w_sensitivity * norm_sensitivity 
        + w_trust_risk * (1 - trust_score)
        + w_access_freq * norm_access_frequency
        - w_data_size * norm_data_size
```

### Default Weights
- Sensitivity: 0.40
- Trust Risk: 0.35
- Access Frequency: 0.15
- Data Size: 0.10

## Benchmark Results

Per PRD FR-9 and Risk R3, the benchmark comparison is part of the requirement itself:

```python
from app.scheduler import benchmark_all_methods

results = benchmark_all_methods(candidates, constraints)
# Returns comparison of all three methods
```

## Limitations

### Current State (Phase 5)
1. **Uses Aer simulator**: Not running on real quantum hardware
2. **No proven advantage**: Quantum advantage not yet demonstrated for this problem
3. **Limited scalability**: Practical on up to ~20 qubits with current simulator

### Honest Assessment
- Classical methods (greedy, SA) are fast and reliable
- QAOA provides research value but no proven improvement yet
- Per SPEC.md 3.10: benchmark comparison must exist before any effectiveness claim

## References

- [IBM Quantum QAOA Tutorial](https://quantum.cloud.ibm.com/docs/en/tutorials/quantum-approximate-optimization-algorithm)
- [Qiskit Documentation](https://qiskit.github.io/qiskit-aer/)
- SPEC.md Section 3.10
- PRD.md FR-9

## Files

- `backend/app/scheduler/prioritizer.py` - Main optimization algorithms
- `backend/app/scheduler/qaoa_builder.py` - Hamiltonian construction
- `backend/app/scheduler/qaoa_optimizer.py` - Qiskit QAOA wrapper
- `backend/tests/test_qaoa_integration.py` - Integration tests
