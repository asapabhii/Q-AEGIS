"""Closed condition-language tests, SPEC.md 3.6."""

import pytest
from pydantic import ValidationError

from app.policy.conditions import (
    LeafCondition,
    MAX_TREE_DEPTH,
    _assert_value_fits_field,
    parse_condition,
    tree_depth,
)


def test_a_leaf_eq_is_accepted() -> None:
    parsed = parse_condition(
        {"field": "sensitivity_label", "op": "eq", "value": "RESTRICTED"}
    )
    assert tree_depth(parsed) == 0


@pytest.mark.parametrize("op", ["eq", "neq"])
def test_eq_and_neq_operators_are_accepted(op: str) -> None:
    parse_condition({"field": "ai_recommendation", "op": op, "value": "allow"})
    parse_condition({"field": "trust_score", "op": op, "value": 0.4})


@pytest.mark.parametrize("op", ["gt", "gte", "lt", "lte"])
def test_inequality_operators_are_accepted_on_numeric_fields(op: str) -> None:
    parse_condition({"field": "trust_score", "op": op, "value": 0.4})


def test_in_operator_requires_a_non_empty_list() -> None:
    parse_condition(
        {
            "field": "sensitivity_label",
            "op": "in",
            "value": ["CONFIDENTIAL", "RESTRICTED"],
        }
    )
    with pytest.raises(ValidationError):
        parse_condition({"field": "sensitivity_label", "op": "in", "value": []})


def test_all_any_and_not_combinators_are_accepted() -> None:
    parse_condition(
        {
            "all": [
                {"field": "sensitivity_label", "op": "eq", "value": "RESTRICTED"},
                {
                    "any": [
                        {"field": "trust_score", "op": "lt", "value": 0.5},
                        {
                            "not": {
                                "field": "ai_recommendation",
                                "op": "eq",
                                "value": "deny",
                            }
                        },
                    ]
                },
            ]
        }
    )


def test_unknown_operator_is_rejected() -> None:
    with pytest.raises(ValidationError):
        parse_condition(
            {"field": "sensitivity_label", "op": "regex", "value": "RESTRICTED"}
        )


def test_unknown_field_is_rejected() -> None:
    with pytest.raises(ValidationError):
        parse_condition({"field": "geo_country", "op": "eq", "value": "IN"})


def test_extra_keys_are_rejected() -> None:
    with pytest.raises(ValidationError):
        parse_condition(
            {
                "field": "sensitivity_label",
                "op": "eq",
                "value": "RESTRICTED",
                "comment": "nope",
            }
        )


def test_empty_all_is_rejected() -> None:
    with pytest.raises(ValidationError):
        parse_condition({"all": []})


def test_inequality_on_a_string_field_is_rejected() -> None:
    with pytest.raises(ValidationError):
        parse_condition({"field": "sensitivity_label", "op": "gt", "value": 0.5})


def test_inequality_requires_a_numeric_value() -> None:
    with pytest.raises(ValidationError):
        parse_condition({"field": "trust_score", "op": "gt", "value": "high"})


def test_inequality_out_of_range_is_rejected() -> None:
    with pytest.raises(ValidationError):
        parse_condition({"field": "trust_score", "op": "gt", "value": 1.5})
    with pytest.raises(ValidationError):
        parse_condition({"field": "risk_value", "op": "lt", "value": -0.01})


def test_in_rejects_nested_lists() -> None:
    with pytest.raises(ValidationError):
        parse_condition(
            {"field": "sensitivity_label", "op": "in", "value": [["RESTRICTED"]]}
        )
    nested = LeafCondition.model_construct(
        field="sensitivity_label",
        op="in",
        value=[["RESTRICTED"]],
    )
    with pytest.raises(ValueError, match="nested"):
        nested.value_must_match_operator_and_field()


def test_eq_rejects_a_list_value() -> None:
    with pytest.raises(ValidationError):
        parse_condition(
            {"field": "sensitivity_label", "op": "eq", "value": ["RESTRICTED"]}
        )


def test_numeric_eq_rejects_a_string() -> None:
    with pytest.raises(ValidationError):
        parse_condition({"field": "trust_score", "op": "eq", "value": "0.5"})


def test_numeric_out_of_range_is_rejected() -> None:
    with pytest.raises(ValidationError):
        parse_condition({"field": "trust_score", "op": "eq", "value": 1.5})
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        _assert_value_fits_field("trust_score", 1.5)
    with pytest.raises(ValueError, match=r"\[0, 1\]"):
        _assert_value_fits_field("risk_value", -0.01)


def test_unknown_sensitivity_label_is_rejected() -> None:
    with pytest.raises(ValidationError):
        parse_condition(
            {"field": "sensitivity_label", "op": "eq", "value": "TOP_SECRET"}
        )


def test_unknown_ai_recommendation_is_rejected() -> None:
    with pytest.raises(ValidationError):
        parse_condition(
            {"field": "ai_recommendation", "op": "eq", "value": "quarantine"}
        )


def test_assert_rejects_an_unknown_field() -> None:
    with pytest.raises(ValueError, match="unknown field"):
        _assert_value_fits_field("geo_country", "IN")


def test_blank_rule_name_is_rejected() -> None:
    from app.policy.schemas import PolicyRuleCreateRequest

    with pytest.raises(ValidationError):
        PolicyRuleCreateRequest(
            rule_name="   ",
            condition_expr={
                "field": "sensitivity_label",
                "op": "eq",
                "value": "RESTRICTED",
            },
            action="deny",
            priority=1,
        )


def test_non_finite_score_is_rejected() -> None:
    from uuid import uuid4

    from app.policy.schemas import PolicyDecisionRequest

    with pytest.raises(ValidationError):
        PolicyDecisionRequest(
            document_id=uuid4(),
            ai_recommendation="allow",
            sensitivity_label="PUBLIC",
            risk_value=float("inf"),
            trust_score=0.2,
        )


def test_tree_deeper_than_the_unrolled_rego_is_rejected() -> None:
    tree: dict = {"field": "trust_score", "op": "lt", "value": 0.5}
    for _ in range(MAX_TREE_DEPTH + 1):
        tree = {"not": tree}
    with pytest.raises(ValueError, match="max depth"):
        parse_condition(tree)
