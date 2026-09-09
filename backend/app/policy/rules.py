"""Rule condition tree parsing and validation.

This module handles the condition_expr jsonb field from policy_rules,
which contains a serialized condition tree from FR-13's rule builder.

Condition tree format:
{
    "op": "eq" | "neq" | "gt" | "gte" | "lt" | "lte" | "in" | "and" | "or" | "not",
    "field": "path.to.field",  # for binary operators
    "value": ...,              # for binary operators
    "children": [...]          # for logical operators (and, or, not)
}

SUPPORTED_OPERATORS: eq, neq, gt, gte, lt, lte, in, and, or, not
SUPPORTED_FIELDS: document_id, sensitivity, trust_score, owner_id, document_status, etc.
"""

from dataclasses import dataclass
from enum import Enum
from typing import Any


class ConditionOperator(str, Enum):
    """Supported condition operators.

    Per SPEC.md 3.6 and AGENTS.md testing requirement:
    one test per condition operator.
    """

    EQ = "eq"
    NEQ = "neq"
    GT = "gt"
    GTE = "gte"
    LT = "lt"
    LTE = "lte"
    IN = "in"
    AND = "and"
    OR = "or"
    NOT = "not"


# Fields that can be used in policy conditions
VALID_FIELDS = frozenset(
    [
        "document_id",
        "sensitivity",
        "trust_score",
        "owner_id",
        "document_status",
        "access_count",
        "last_accessed_at",
        "tags",
        "file_type",
        "created_at",
        "classification_confidence",
    ]
)


class InvalidConditionError(ValueError):
    """Raised when a condition tree is malformed or invalid."""

    pass


@dataclass(frozen=True)
class ConditionNode:
    """Represents a node in the condition tree.

    Attributes:
        operator: The operator for this node.
        field: The field path (for binary operators).
        value: The value to compare against (for binary operators).
        children: Child nodes (for logical operators).
    """

    operator: ConditionOperator
    field: str | None = None
    value: Any = None
    children: tuple["ConditionNode", ...] = ()


def validate_condition_tree(tree: dict[str, Any], path: str = "root") -> None:
    """Validate a condition tree structure.

    Args:
        tree: The condition tree to validate.
        path: Current path in the tree (for error messages).

    Raises:
        InvalidConditionError: If the tree is malformed.
    """
    if not isinstance(tree, dict):
        raise InvalidConditionError(
            f"Condition at {path} must be a dict, got {type(tree).__name__}"
        )

    if "op" not in tree:
        raise InvalidConditionError(f"Condition at {path} missing 'op' field")

    op = tree["op"]
    try:
        operator = ConditionOperator(op)
    except ValueError:
        valid_ops = [o.value for o in ConditionOperator]
        raise InvalidConditionError(
            f"Condition at {path} has invalid operator '{op}'. "
            f"Valid operators: {valid_ops}"
        )

    # Binary operators require field and value
    if operator in (
        ConditionOperator.EQ,
        ConditionOperator.NEQ,
        ConditionOperator.GT,
        ConditionOperator.GTE,
        ConditionOperator.LT,
        ConditionOperator.LTE,
        ConditionOperator.IN,
    ):
        if "field" not in tree:
            raise InvalidConditionError(
                f"Binary operator '{op}' at {path} requires 'field'"
            )
        field = tree["field"]
        if field not in VALID_FIELDS:
            raise InvalidConditionError(
                f"Field '{field}' at {path} is not valid. "
                f"Valid fields: {sorted(VALID_FIELDS)}"
            )
        if "value" not in tree:
            raise InvalidConditionError(
                f"Binary operator '{op}' at {path} requires 'value'"
            )

    # Logical operators require children
    if operator in (ConditionOperator.AND, ConditionOperator.OR):
        if "children" not in tree or not isinstance(tree["children"], list):
            raise InvalidConditionError(
                f"Logical operator '{op}' at {path} requires 'children' list"
            )
        if len(tree["children"]) != 2:
            raise InvalidConditionError(
                f"Logical operator '{op}' at {path} requires exactly 2 children, "
                f"got {len(tree.get('children', []))}"
            )
        for i, child in enumerate(tree["children"]):
            validate_condition_tree(child, f"{path}.children[{i}]")

    if operator == ConditionOperator.NOT:
        if "children" not in tree or not isinstance(tree["children"], list):
            raise InvalidConditionError(
                f"NOT operator at {path} requires 'children' list"
            )
        if len(tree["children"]) != 1:
            raise InvalidConditionError(
                f"NOT operator at {path} requires exactly 1 child, "
                f"got {len(tree.get('children', []))}"
            )
        validate_condition_tree(tree["children"][0], f"{path}.children[0]")


def parse_condition_tree(tree: dict[str, Any]) -> ConditionNode:
    """Parse a condition tree into a ConditionNode structure.

    Args:
        tree: The condition tree from policy_rules.condition_expr.

    Returns:
        A ConditionNode representing the tree.

    Raises:
        InvalidConditionError: If the tree is malformed.
    """
    validate_condition_tree(tree)

    op = ConditionOperator(tree["op"])

    # Base case: binary operator
    if op in (
        ConditionOperator.EQ,
        ConditionOperator.NEQ,
        ConditionOperator.GT,
        ConditionOperator.GTE,
        ConditionOperator.LT,
        ConditionOperator.LTE,
        ConditionOperator.IN,
    ):
        return ConditionNode(
            operator=op,
            field=tree["field"],
            value=tree["value"],
        )

    # Logical operators: parse children
    if op in (ConditionOperator.AND, ConditionOperator.OR):
        children = tuple(parse_condition_tree(c) for c in tree["children"])
        return ConditionNode(operator=op, children=children)

    if op == ConditionOperator.NOT:
        children = (parse_condition_tree(tree["children"][0]),)
        return ConditionNode(operator=op, children=children)

    # Should not reach here
    raise InvalidConditionError(f"Unknown operator: {op}")


def prepare_rego_input(
    rules: list[dict[str, Any]], context: dict[str, Any]
) -> dict[str, Any]:
    """Prepare input for OPA Rego evaluation.

    This converts the database representation to what the Rego
    evaluator.rego module expects.

    Args:
        rules: List of policy rule dictionaries from the database.
        context: Document context dictionary.

    Returns:
        Input structure for OPA.
    """
    return {
        "rules": rules,
        "context": context,
    }
