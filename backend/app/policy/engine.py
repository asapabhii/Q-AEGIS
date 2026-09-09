"""In-process policy evaluator, ``SPEC.md`` 3.6, ``PRD.md`` FR-5.

Loads the compiled WASM bundle and evaluates it with ``opa-wasmtime``. Rules
are passed as input data, never compiled into Rego. The host sorts active
rules by ascending priority before evaluation; the first match in that order
wins.

``object.get`` and ``count`` are provided as in-process host builtins. Network
builtins are not provided and are banned at compile time by
``rego/capabilities.json``.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any
from uuid import UUID

from opa_wasmtime import OPAPolicy

from app.db.enums import PolicyAction
from app.policy.conditions import parse_condition

#: Recorded on every ``policy_decisions`` audit payload.
POLICY_VERSION = "policy-first-match-0.1.0"

WASM_PATH = Path(__file__).resolve().parent / "rego" / "policy.wasm"

#: Host implementations for builtins the WASM module imports. In-process only.
_HOST_BUILTINS = {
    "object.get": lambda obj, key, default: (
        obj[key] if isinstance(obj, dict) and key in obj else default
    ),
    "count": lambda value: len(value),
}


class PolicyEngineError(RuntimeError):
    """The WASM evaluator could not produce a decision from a valid input."""


@dataclass(frozen=True)
class EvaluableRule:
    """One active rule, already validated, in the order the engine should try."""

    id: UUID
    rule_name: str
    action: PolicyAction
    condition: dict[str, Any]


@dataclass(frozen=True)
class DocumentFacts:
    """Closed v1 evaluation input. Every field is required."""

    sensitivity_label: str
    risk_value: float
    trust_score: float
    ai_recommendation: PolicyAction

    def as_json(self) -> dict[str, str | float]:
        """JSON primitives for the WASM input and the audit payload."""
        return {
            "sensitivity_label": self.sensitivity_label,
            "risk_value": self.risk_value,
            "trust_score": self.trust_score,
            "ai_recommendation": self.ai_recommendation.value,
        }


@dataclass(frozen=True)
class PolicyEvalResult:
    """Outcome of one pass through the gate."""

    rule_id: UUID | None
    rule_name: str | None
    ai_recommendation: PolicyAction
    final_decision: PolicyAction
    overridden: bool
    policy_version: str


@lru_cache(maxsize=1)
def _load_policy() -> OPAPolicy:
    """Load the committed WASM bundle once per process."""
    if not WASM_PATH.is_file():
        raise PolicyEngineError(
            f"Policy WASM bundle is missing at {WASM_PATH}. Rebuild it with "
            "`opa build -t wasm -e q_aegis/policy/first_match` (OPA 1.8.0)."
        )
    return OPAPolicy(str(WASM_PATH), builtins=_HOST_BUILTINS)


def evaluate(
    facts: DocumentFacts,
    rules: list[EvaluableRule],
) -> PolicyEvalResult:
    """Return the first matching rule's action, or the AI recommendation.

    ``rules`` must already be sorted by ascending priority. Inactive rules must
    not be included. Each condition is re-validated here so a corrupt stored
    tree fails the request rather than being skipped (skipping a deny is
    fail-open).
    """
    prepared: list[dict[str, Any]] = []
    by_id: dict[str, EvaluableRule] = {}
    for rule in rules:
        parse_condition(rule.condition)
        rule_id = str(rule.id)
        prepared.append(
            {
                "id": rule_id,
                "action": rule.action.value,
                "condition": rule.condition,
            }
        )
        by_id[rule_id] = rule

    raw = _load_policy().evaluate({"document": facts.as_json(), "rules": prepared})
    matched = _first_result(raw)
    if matched is None:
        return PolicyEvalResult(
            rule_id=None,
            rule_name=None,
            ai_recommendation=facts.ai_recommendation,
            final_decision=facts.ai_recommendation,
            overridden=False,
            policy_version=POLICY_VERSION,
        )

    matched_id = matched.get("id")
    if not isinstance(matched_id, str) or matched_id not in by_id:
        raise PolicyEngineError(f"WASM returned an unknown rule id {matched_id!r}.")
    winner = by_id[matched_id]
    return PolicyEvalResult(
        rule_id=winner.id,
        rule_name=winner.rule_name,
        ai_recommendation=facts.ai_recommendation,
        final_decision=winner.action,
        overridden=winner.action != facts.ai_recommendation,
        policy_version=POLICY_VERSION,
    )


def _first_result(raw: object) -> dict[str, Any] | None:
    """Parse the OPA WASM envelope ``[{'result': ...}]`` or ``[]``."""
    if raw in (None, [], {}):
        return None
    if not isinstance(raw, list) or not raw:
        raise PolicyEngineError(f"Unexpected WASM envelope: {raw!r}")
    item = raw[0]
    if not isinstance(item, dict) or "result" not in item:
        raise PolicyEngineError(f"Unexpected WASM envelope: {raw!r}")
    result = item["result"]
    if result in (None, {}, []):
        return None
    if not isinstance(result, dict):
        raise PolicyEngineError(f"Unexpected WASM result: {result!r}")
    return result
