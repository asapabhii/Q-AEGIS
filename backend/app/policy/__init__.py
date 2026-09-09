"""Policy engine for deterministic rule-based overrides, `SPEC.md` 3.6, `PRD.md` FR-5.

This module evaluates policy rules against document context to determine whether
an AI recommendation should be overridden. Rules are data (jsonb condition trees),
not generated Rego code - they are interpreted by a fixed Rego module.

Four constraints (per SPEC.md 3.6):
1. Rules are data, not policy source - condition_expr holds serialized condition trees
2. Evaluation is in-process via WebAssembly bundle (no sidecar, no network)
3. Determinism enforced by capabilities file in CI (opa check --capabilities)
4. Priority-ordered first match - lowest priority value wins

SECURITY: This module sits directly between an AI recommendation and a real
security decision. Errors here have worse consequences than elsewhere.
"""

from app.policy.engine import PolicyEngine, evaluate_policy_decision, get_policy_engine

__all__ = [
    "PolicyEngine",
    "evaluate_policy_decision",
    "get_policy_engine",
]