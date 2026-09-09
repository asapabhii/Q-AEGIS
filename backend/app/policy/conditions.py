"""Closed v1 condition tree for ``policy_rules.condition_expr``.

The tree is data, not policy source. One reviewed Rego module interprets it.
Unknown operators, unknown fields, extra keys, empty combinators, and null
values are rejected here so they never reach the scorer or the WASM evaluator.

Combinators: ``all``, ``any``, ``not``.
Leaf operators: ``eq``, ``neq``, ``gt``, ``gte``, ``lt``, ``lte``, ``in``.
Fields: ``sensitivity_label``, ``risk_value``, ``trust_score``, ``ai_recommendation``.
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, TypeAdapter, model_validator

from app.classifier.labels import SensitivityLabel
from app.db.enums import PolicyAction

CONDITION_FIELDS: tuple[str, ...] = (
    "sensitivity_label",
    "risk_value",
    "trust_score",
    "ai_recommendation",
)

LEAF_OPERATORS: tuple[str, ...] = (
    "eq",
    "neq",
    "gt",
    "gte",
    "lt",
    "lte",
    "in",
)

NUMERIC_FIELDS: frozenset[str] = frozenset({"risk_value", "trust_score"})

#: Combinator nesting the unrolled Rego can evaluate. Deeper trees are 422.
MAX_TREE_DEPTH = 8

JsonScalar = str | int | float | bool


class LeafCondition(BaseModel):
    """A comparison of one document field against a value."""

    model_config = ConfigDict(extra="forbid")

    field: Literal[
        "sensitivity_label",
        "risk_value",
        "trust_score",
        "ai_recommendation",
    ]
    op: Literal["eq", "neq", "gt", "gte", "lt", "lte", "in"]
    value: JsonScalar | list[JsonScalar]

    @model_validator(mode="after")
    def value_must_match_operator_and_field(self) -> "LeafCondition":
        """Inequality is numeric-only; ``in`` takes a non-empty list."""
        if self.op in {"gt", "gte", "lt", "lte"}:
            if self.field not in NUMERIC_FIELDS:
                raise ValueError(
                    f"{self.op} is only valid on numeric fields, not {self.field}"
                )
            _assert_value_fits_field(self.field, self.value)
        elif self.op == "in":
            if not isinstance(self.value, list) or len(self.value) < 1:
                raise ValueError("in requires a non-empty list")
            if any(isinstance(item, list) for item in self.value):
                raise ValueError("in does not accept nested lists")
        else:
            if isinstance(self.value, list):
                raise ValueError(f"{self.op} cannot take a list; use in")
            _assert_value_fits_field(self.field, self.value)
        if self.op == "in":
            for item in self.value:  # type: ignore[union-attr]
                _assert_value_fits_field(self.field, item)
        return self


class AllCondition(BaseModel):
    """True when every child is true. Empty ``all`` is rejected (would be vacuous)."""

    model_config = ConfigDict(extra="forbid")

    all: list[Condition] = Field(min_length=1)


class AnyCondition(BaseModel):
    """True when at least one child is true."""

    model_config = ConfigDict(extra="forbid")

    any: list[Condition] = Field(min_length=1)


class NotCondition(BaseModel):
    """True when the child is not true."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    not_: Condition = Field(alias="not")


# Forward ref for combinators; rebuilt below.
Condition = AllCondition | AnyCondition | NotCondition | LeafCondition

AllCondition.model_rebuild()
AnyCondition.model_rebuild()
NotCondition.model_rebuild()

CONDITION_ADAPTER: TypeAdapter[Condition] = TypeAdapter(Condition)


def parse_condition(raw: Any) -> Condition:
    """Validate a stored or submitted condition tree.

    Raises:
        pydantic.ValidationError: if the tree is not in the closed v1 language.
        ValueError: if the tree is deeper than :data:`MAX_TREE_DEPTH`.
    """
    parsed = CONDITION_ADAPTER.validate_python(raw)
    depth = tree_depth(parsed)
    if depth > MAX_TREE_DEPTH:
        raise ValueError(
            f"condition tree exceeds max depth {MAX_TREE_DEPTH} (got {depth})"
        )
    return parsed


def tree_depth(condition: Condition) -> int:
    """Combinator nesting. A leaf is depth 0."""
    if isinstance(condition, LeafCondition):
        return 0
    if isinstance(condition, NotCondition):
        return 1 + tree_depth(condition.not_)
    children = condition.all if isinstance(condition, AllCondition) else condition.any
    return 1 + max(tree_depth(child) for child in children)


def condition_as_json(condition: Condition) -> dict[str, Any]:
    """JSON-ready tree using the stored key ``not``, not the Python alias."""
    return condition.model_dump(by_alias=True, mode="json")


def _is_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _assert_value_fits_field(field: str, value: object) -> None:
    if field in NUMERIC_FIELDS:
        if not _is_number(value):
            raise ValueError(f"{field} requires a numeric value")
        number = float(value)  # type: ignore[arg-type]
        if number < 0.0 or number > 1.0:
            raise ValueError(f"{field} must be in [0, 1]")
        return
    if field == "sensitivity_label":
        if not isinstance(value, str) or value not in {
            label.value for label in SensitivityLabel
        }:
            raise ValueError("sensitivity_label must be a known label")
        return
    if field == "ai_recommendation":
        if not isinstance(value, str) or value not in {
            action.value for action in PolicyAction
        }:
            raise ValueError("ai_recommendation must be a known policy action")
        return
    raise ValueError(f"unknown field {field}")
