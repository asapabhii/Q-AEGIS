"""Pydantic schemas for the policy engine.

These models define the data structures for policy rules, decisions,
and the context passed to OPA for evaluation.
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

# Use the PolicyAction from db.enums directly (no duplication)
from app.db.enums import PolicyAction as PolicyActionEnum


# Type alias for clarity
PolicyAction = PolicyActionEnum


@dataclass(frozen=True)
class PolicyRule:
    """A single policy rule from the database.

    Attributes:
        id: UUID of the policy rule.
        rule_name: Unique name for the rule.
        condition_expr: Serialized condition tree from FR-13's rule builder.
        action: The action to take when this rule matches.
        priority: Lower value = evaluated first.
        active: Whether the rule is currently active.
    """

    id: UUID
    rule_name: str
    condition_expr: dict[str, Any]
    action: PolicyAction
    priority: int
    active: bool = True


@dataclass(frozen=True)
class PolicyContext:
    """Context about a document for policy evaluation.

    This is what gets passed to OPA alongside the rules.
    Contains the document's current state including sensitivity,
    trust score, and other relevant fields.
    """

    document_id: UUID
    sensitivity: str
    trust_score: float
    owner_id: UUID | None = None
    document_status: str | None = None
    access_count: int | None = None
    last_accessed_at: str | None = None
    tags: list[str] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for OPA input."""
        result = {
            "document_id": str(self.document_id),
            "sensitivity": self.sensitivity,
            "trust_score": self.trust_score,
        }
        if self.owner_id:
            result["owner_id"] = str(self.owner_id)
        if self.document_status:
            result["document_status"] = self.document_status
        if self.access_count is not None:
            result["access_count"] = self.access_count
        if self.last_accessed_at:
            result["last_accessed_at"] = self.last_accessed_at
        if self.tags:
            result["tags"] = self.tags
        return result


@dataclass(frozen=True)
class PolicyDecision:
    """Result of policy evaluation.

    Attributes:
        matched: Whether any rule matched.
        rule_id: UUID of the matching rule, or None if no match.
        rule_name: Name of the matching rule, or None.
        action: The action to take (from the rule), or None.
        rationale: Human-readable explanation of the decision.
        ai_recommendation: The original AI recommendation (passed through).
        final_decision: The final decision after policy gate.
    """

    matched: bool
    rule_id: UUID | None
    rule_name: str | None
    action: PolicyAction | None
    rationale: str
    ai_recommendation: PolicyAction
    final_decision: PolicyAction


def build_policy_input(
    rules: list[PolicyRule],
    context: PolicyContext,
) -> dict[str, Any]:
    """Build the input structure for OPA evaluation.

    Args:
        rules: Active policy rules to evaluate.
        context: Document context for evaluation.

    Returns:
        Dictionary structured for the Rego evaluator module.
    """
    return {
        "rules": [
            {
                "id": str(rule.id),
                "rule_name": rule.rule_name,
                "condition_expr": rule.condition_expr,
                "action": rule.action.value,
                "priority": rule.priority,
            }
            for rule in rules
        ],
        "context": context.to_dict(),
    }