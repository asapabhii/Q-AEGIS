"""Policy engine for deterministic rule-based overrides, `SPEC.md` 3.6, `PRD.md` FR-5.

Evaluates a closed condition tree against caller-supplied document facts and
returns the first matching active rule's action, or the AI recommendation when
nothing matches. Evaluation is in-process WASM (`opa-wasmtime`) over one
reviewed Rego module. Rules are data on `input`, never compiled into Rego.

`after_hours`-style derivation is not this module's job. `trust_score` and
`ai_recommendation` are facts the caller sends until 3.5 and 3.7 exist.

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

Owner: Udhav (`WORK_DIVISION.md`). Required reviewer on any change here.
"""

from app.policy.engine import (
    DocumentFacts,
    EvaluableRule,
    PolicyEngineError,
    PolicyEvalResult,
    evaluate,
)

__all__ = [
    "DocumentFacts",
    "EvaluableRule",
    "PolicyEngineError",
    "PolicyEvalResult",
    "evaluate",
]
