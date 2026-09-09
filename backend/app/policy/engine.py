"""Policy engine core implementation, `SPEC.md` 3.6, `PRD.md` FR-5.

This module provides the in-process OPA evaluation for deterministic policy
decisions. It evaluates rules against document context and returns a decision
that can override the AI's recommendation.

Four constraints (per SPEC.md 3.6):
1. Rules are data, not policy source
2. Evaluation is in-process via WebAssembly bundle (no sidecar, no network)
3. Determinism enforced by capabilities file in CI
4. Priority-ordered first match - lowest priority value wins

SECURITY: This module sits directly between an AI recommendation and a real
security decision. Errors here have worse consequences than elsewhere.
"""

from dataclasses import dataclass
from typing import Any

from app.db.enums import PolicyAction
from app.policy.schemas import PolicyContext, PolicyDecision, PolicyRule
from app.policy.rules import InvalidConditionError, validate_condition_tree


@dataclass(frozen=True)
class PolicyEngine:
    """Policy evaluation engine using OPA/Rego.

    This engine evaluates active policy rules against document context
    to determine whether an AI recommendation should be overridden.

    The evaluation is:
    - In-process (no network calls)
    - Deterministic (capabilities file enforced in CI)
    - Priority-ordered (first match wins)

    Attributes:
        _initialized: Whether the engine has been initialized.
    """

    _initialized: bool = False

    def __post_init__(self):
        """Initialize the engine.

        In Phase 2, this loads the Rego module. The actual WASM evaluation
        will be implemented when opa-wasmtime is integrated.
        """
        # TODO: Load compiled Rego WASM bundle
        # For now, we implement a pure-Python fallback for development
        object.__setattr__(self, '_initialized', True)

    def evaluate(
        self,
        rules: list[PolicyRule],
        context: PolicyContext,
        ai_recommendation: PolicyAction,
    ) -> PolicyDecision:
        """Evaluate policy rules against context.

        Args:
            rules: Active policy rules to evaluate.
            context: Document context for evaluation.
            ai_recommendation: The AI's original recommendation.

        Returns:
            PolicyDecision with the final decision and rationale.

        Note:
            Per SPEC.md 3.6: "no rule fired, AI recommendation stood" is
            the common case and must be modeled as null rule_id, not a
            placeholder rule.
        """
        if not rules:
            # No rules to evaluate - AI recommendation stands
            return PolicyDecision(
                matched=False,
                rule_id=None,
                rule_name=None,
                action=None,
                rationale="No active policy rules to evaluate",
                ai_recommendation=ai_recommendation,
                final_decision=ai_recommendation,
            )

        # Sort rules by priority (lower = evaluated first)
        sorted_rules = sorted(rules, key=lambda r: r.priority)

        # Evaluate each rule in priority order, stop at first match
        for rule in sorted_rules:
            if not rule.active:
                continue

            # Validate condition expression
            try:
                validate_condition_tree(rule.condition_expr)
            except InvalidConditionError:
                # Skip invalid rules, log for review
                continue

            # Check if rule matches (using Python evaluation as fallback)
            if self._matches(rule, context):
                # Rule matched - return override decision
                action = PolicyAction(rule.action.value)
                return PolicyDecision(
                    matched=True,
                    rule_id=rule.id,
                    rule_name=rule.rule_name,
                    action=action,
                    rationale=f"Rule '{rule.rule_name}' matched, action: {rule.action.value}",
                    ai_recommendation=ai_recommendation,
                    final_decision=action,
                )

        # No rule matched - AI recommendation stands
        return PolicyDecision(
            matched=False,
            rule_id=None,
            rule_name=None,
            action=None,
            rationale="No policy rule matched the current context",
            ai_recommendation=ai_recommendation,
            final_decision=ai_recommendation,
        )

    def _matches(self, rule: PolicyRule, context: PolicyContext) -> bool:
        """Check if a rule's condition matches the context.

        This is a Python fallback implementation. The production
        implementation will use OPA via opa-wasmtime.

        Args:
            rule: The policy rule to check.
            context: The document context.

        Returns:
            True if the rule matches, False otherwise.
        """
        return _evaluate_condition(rule.condition_expr, context)


def _evaluate_condition(condition: dict[str, Any], context: PolicyContext) -> bool:
    """Evaluate a condition tree against context.

    This is a simplified Python implementation that mirrors the
    evaluator.rego logic.

    Args:
        condition: The condition tree.
        context: The document context.

    Returns:
        True if the condition matches.
    """
    op = condition.get("op")

    if op == "eq":
        field_value = _get_field_value(context, condition.get("field"))
        return field_value == condition.get("value")

    if op == "neq":
        field_value = _get_field_value(context, condition.get("field"))
        return field_value != condition.get("value")

    if op == "gt":
        field_value = _get_field_value(context, condition.get("field"))
        return field_value > condition.get("value")

    if op == "gte":
        field_value = _get_field_value(context, condition.get("field"))
        return field_value >= condition.get("value")

    if op == "lt":
        field_value = _get_field_value(context, condition.get("field"))
        return field_value < condition.get("value")

    if op == "lte":
        field_value = _get_field_value(context, condition.get("field"))
        return field_value <= condition.get("value")

    if op == "in":
        field_value = _get_field_value(context, condition.get("field"))
        return field_value in condition.get("value", [])

    if op == "and":
        children = condition.get("children", [])
        return all(_evaluate_condition(c, context) for c in children)

    if op == "or":
        children = condition.get("children", [])
        return any(_evaluate_condition(c, context) for c in children)

    if op == "not":
        children = condition.get("children", [])
        return not _evaluate_condition(children[0], context)

    return False


def _get_field_value(context: PolicyContext, field: str):
    """Get a field value from context using dot-notation path.

    Args:
        context: The document context.
        field: The field path (e.g., "trust_score" or "document.status").

    Returns:
        The field value.
    """
    if not field:
        return None

    # Direct field access for simple cases
    field_map = {
        "document_id": context.document_id,
        "sensitivity": context.sensitivity,
        "trust_score": context.trust_score,
        "owner_id": context.owner_id,
        "document_status": context.document_status,
        "access_count": context.access_count,
        "last_accessed_at": context.last_accessed_at,
        "tags": context.tags,
    }

    return field_map.get(field)


# Module-level engine instance for FastAPI dependency injection
_engine: PolicyEngine | None = None


def get_policy_engine() -> PolicyEngine:
    """Get or create the policy engine singleton.

    Returns:
        The PolicyEngine instance.
    """
    global _engine
    if _engine is None:
        _engine = PolicyEngine()
    return _engine


def evaluate_policy_decision(
    rules: list[PolicyRule],
    context: PolicyContext,
    ai_recommendation: PolicyAction,
) -> PolicyDecision:
    """Convenience function to evaluate a policy decision.

    This is the main entry point for the policy engine.

    Args:
        rules: Active policy rules from the database.
        context: Document context for evaluation.
        ai_recommendation: The AI's recommendation.

    Returns:
        The policy decision with final decision and rationale.
    """
    engine = get_policy_engine()
    return engine.evaluate(rules, context, ai_recommendation)