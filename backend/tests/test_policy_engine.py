"""WASM evaluator tests, SPEC.md 3.6.

One case per leaf operator and per policy action, plus first-match and the
no-rule-fired path. No database.
"""

from uuid import uuid4

import pytest

from app.db.enums import PolicyAction
from app.policy.engine import (
    POLICY_VERSION,
    DocumentFacts,
    EvaluableRule,
    PolicyEngineError,
    evaluate,
)


def _facts(
    *,
    sensitivity_label: str = "RESTRICTED",
    risk_value: float = 0.2,
    trust_score: float = 0.3,
    ai_recommendation: PolicyAction = PolicyAction.ALLOW,
) -> DocumentFacts:
    return DocumentFacts(
        sensitivity_label=sensitivity_label,
        risk_value=risk_value,
        trust_score=trust_score,
        ai_recommendation=ai_recommendation,
    )


def _rule(
    condition: dict,
    *,
    action: PolicyAction = PolicyAction.DENY,
    name: str = "r",
) -> EvaluableRule:
    return EvaluableRule(
        id=uuid4(),
        rule_name=name,
        action=action,
        condition=condition,
    )


def test_no_rules_leaves_the_ai_recommendation_standing() -> None:
    result = evaluate(_facts(), [])
    assert result.rule_id is None
    assert result.final_decision is PolicyAction.ALLOW
    assert result.overridden is False
    assert result.policy_version == POLICY_VERSION


def test_eq_match_overrides_with_the_rule_action() -> None:
    rule = _rule({"field": "sensitivity_label", "op": "eq", "value": "RESTRICTED"})
    result = evaluate(_facts(), [rule])
    assert result.rule_id == rule.id
    assert result.final_decision is PolicyAction.DENY
    assert result.overridden is True


def test_eq_miss_does_not_fire() -> None:
    rule = _rule({"field": "sensitivity_label", "op": "eq", "value": "PUBLIC"})
    result = evaluate(_facts(), [rule])
    assert result.rule_id is None
    assert result.overridden is False


def test_neq_operator() -> None:
    rule = _rule({"field": "ai_recommendation", "op": "neq", "value": "deny"})
    result = evaluate(_facts(), [rule])
    assert result.rule_id == rule.id


@pytest.mark.parametrize(
    ("op", "value", "should_match"),
    [
        ("gt", 0.2, True),
        ("gt", 0.3, False),
        ("gte", 0.3, True),
        ("lt", 0.4, True),
        ("lt", 0.3, False),
        ("lte", 0.3, True),
    ],
)
def test_numeric_operators(op: str, value: float, should_match: bool) -> None:
    rule = _rule({"field": "trust_score", "op": op, "value": value})
    result = evaluate(_facts(trust_score=0.3), [rule])
    assert (result.rule_id == rule.id) is should_match


def test_in_operator() -> None:
    rule = _rule(
        {
            "field": "sensitivity_label",
            "op": "in",
            "value": ["CONFIDENTIAL", "RESTRICTED"],
        }
    )
    result = evaluate(_facts(), [rule])
    assert result.rule_id == rule.id


def test_all_requires_every_child() -> None:
    rule = _rule(
        {
            "all": [
                {"field": "sensitivity_label", "op": "eq", "value": "RESTRICTED"},
                {"field": "trust_score", "op": "lt", "value": 0.1},
            ]
        }
    )
    result = evaluate(_facts(trust_score=0.3), [rule])
    assert result.rule_id is None


def test_any_fires_when_one_child_matches() -> None:
    rule = _rule(
        {
            "any": [
                {"field": "sensitivity_label", "op": "eq", "value": "PUBLIC"},
                {"field": "trust_score", "op": "lt", "value": 0.5},
            ]
        }
    )
    result = evaluate(_facts(), [rule])
    assert result.rule_id == rule.id


def test_not_inverts_the_child() -> None:
    rule = _rule({"not": {"field": "sensitivity_label", "op": "eq", "value": "PUBLIC"}})
    result = evaluate(_facts(), [rule])
    assert result.rule_id == rule.id


@pytest.mark.parametrize("action", list(PolicyAction))
def test_each_rule_action_can_become_the_final_decision(
    action: PolicyAction,
) -> None:
    rule = _rule(
        {"field": "sensitivity_label", "op": "eq", "value": "RESTRICTED"},
        action=action,
    )
    result = evaluate(_facts(), [rule])
    assert result.final_decision is action
    assert result.overridden is (action is not PolicyAction.ALLOW)


def test_first_rule_in_the_supplied_order_wins() -> None:
    """The host sorts by priority; the engine must not reorder."""
    later = _rule(
        {"field": "sensitivity_label", "op": "eq", "value": "RESTRICTED"},
        action=PolicyAction.DENY,
        name="later",
    )
    earlier = _rule(
        {"field": "sensitivity_label", "op": "eq", "value": "RESTRICTED"},
        action=PolicyAction.REQUIRE_MFA,
        name="earlier",
    )
    result = evaluate(_facts(), [earlier, later])
    assert result.rule_id == earlier.id
    assert result.final_decision is PolicyAction.REQUIRE_MFA


def test_max_combinator_depth_still_evaluates() -> None:
    """Eight nested ``not``s of a matching leaf is still a match (even inversion)."""
    tree: dict = {
        "field": "sensitivity_label",
        "op": "eq",
        "value": "RESTRICTED",
    }
    for _ in range(8):
        tree = {"not": tree}
    result = evaluate(_facts(), [_rule(tree)])
    assert result.rule_id is not None


def test_missing_wasm_bundle_is_an_engine_error(
    monkeypatch: pytest.MonkeyPatch, tmp_path
) -> None:
    from app.policy import engine as engine_mod

    monkeypatch.setattr(engine_mod, "WASM_PATH", tmp_path / "missing.wasm")
    engine_mod._load_policy.cache_clear()
    try:
        with pytest.raises(PolicyEngineError, match="missing"):
            evaluate(_facts(), [])
    finally:
        engine_mod._load_policy.cache_clear()


def test_unexpected_wasm_envelope_is_an_engine_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakePolicy:
        def evaluate(self, _input: object) -> object:
            return {"not": "an envelope"}

    monkeypatch.setattr("app.policy.engine._load_policy", lambda: FakePolicy())
    with pytest.raises(PolicyEngineError, match="Unexpected WASM envelope"):
        evaluate(_facts(), [])


def test_unknown_rule_id_from_wasm_is_an_engine_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakePolicy:
        def evaluate(self, _input: object) -> object:
            return [{"result": {"id": "not-a-stored-rule"}}]

    monkeypatch.setattr("app.policy.engine._load_policy", lambda: FakePolicy())
    with pytest.raises(PolicyEngineError, match="unknown rule id"):
        evaluate(_facts(), [])


def test_envelope_item_that_is_not_an_object_is_an_engine_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakePolicy:
        def evaluate(self, _input: object) -> object:
            return ["not-an-object"]

    monkeypatch.setattr("app.policy.engine._load_policy", lambda: FakePolicy())
    with pytest.raises(PolicyEngineError, match="Unexpected WASM envelope"):
        evaluate(_facts(), [])


def test_non_object_result_is_an_engine_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakePolicy:
        def evaluate(self, _input: object) -> object:
            return [{"result": "deny"}]

    monkeypatch.setattr("app.policy.engine._load_policy", lambda: FakePolicy())
    with pytest.raises(PolicyEngineError, match="Unexpected WASM result"):
        evaluate(_facts(), [])


def test_empty_result_object_is_treated_as_no_match(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class FakePolicy:
        def evaluate(self, _input: object) -> object:
            return [{"result": {}}]

    monkeypatch.setattr("app.policy.engine._load_policy", lambda: FakePolicy())
    result = evaluate(_facts(), [])
    assert result.rule_id is None
    assert result.overridden is False
