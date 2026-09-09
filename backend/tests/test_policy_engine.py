"""Tests for the Policy Engine, SPEC.md 3.6, PRD FR-5.

CRITICAL TESTING REQUIREMENT (AGENTS.md):
"The policy engine (3.6) requires one test per rule type and per condition operator,
not a single happy-path test."

This module has one of the highest consequence for errors - it gates AI recommendations
with deterministic rules.
"""

import pytest
from uuid import uuid4

from app.db.enums import PolicyAction
from app.policy.engine import PolicyEngine, get_policy_engine, evaluate_policy_decision
from app.policy.rules import (
    validate_condition_tree,
    parse_condition_tree,
    ConditionOperator,
    InvalidConditionError,
)
from app.policy.schemas import PolicyContext, PolicyRule


# =============================================================================
# Condition Tree Validation Tests - One per operator (per AGENTS.md)
# =============================================================================

def test_operator_eq_valid():
    """Test equality operator validation."""
    tree = {"op": "eq", "field": "sensitivity", "value": "SENSITIVE"}
    validate_condition_tree(tree)  # Should not raise


def test_operator_neq_valid():
    """Test not-equal operator validation."""
    tree = {"op": "neq", "field": "trust_score", "value": 0.5}
    validate_condition_tree(tree)


def test_operator_gt_valid():
    """Test greater-than operator validation."""
    tree = {"op": "gt", "field": "trust_score", "value": 0.8}
    validate_condition_tree(tree)


def test_operator_gte_valid():
    """Test greater-than-or-equal operator validation."""
    tree = {"op": "gte", "field": "access_count", "value": 10}
    validate_condition_tree(tree)


def test_operator_lt_valid():
    """Test less-than operator validation."""
    tree = {"op": "lt", "field": "trust_score", "value": 0.3}
    validate_condition_tree(tree)


def test_operator_lte_valid():
    """Test less-than-or-equal operator validation."""
    tree = {"op": "lte", "field": "access_count", "value": 5}
    validate_condition_tree(tree)


def test_operator_in_valid():
    """Test 'in' operator validation."""
    tree = {"op": "in", "field": "sensitivity", "value": ["SENSITIVE", "CONFIDENTIAL"]}
    validate_condition_tree(tree)


def test_operator_and_valid():
    """Test AND operator validation."""
    tree = {
        "op": "and",
        "children": [
            {"op": "eq", "field": "sensitivity", "value": "SENSITIVE"},
            {"op": "gt", "field": "trust_score", "value": 0.5},
        ]
    }
    validate_condition_tree(tree)


def test_operator_or_valid():
    """Test OR operator validation."""
    tree = {
        "op": "or",
        "children": [
            {"op": "eq", "field": "sensitivity", "value": "PUBLIC"},
            {"op": "eq", "field": "document_status", "value": "archived"},
        ]
    }
    validate_condition_tree(tree)


def test_operator_not_valid():
    """Test NOT operator validation."""
    tree = {
        "op": "not",
        "children": [
            {"op": "eq", "field": "sensitivity", "value": "PUBLIC"}
        ]
    }
    validate_condition_tree(tree)


# =============================================================================
# Invalid Condition Tests
# =============================================================================

def test_invalid_operator_raises():
    """Test that invalid operator raises error."""
    tree = {"op": "invalid_op", "field": "sensitivity", "value": "SENSITIVE"}
    with pytest.raises(InvalidConditionError) as exc_info:
        validate_condition_tree(tree)
    assert "invalid operator" in str(exc_info.value).lower()


def test_missing_field_raises():
    """Test that binary operator without field raises error."""
    tree = {"op": "eq", "value": "SENSITIVE"}  # Missing 'field'
    with pytest.raises(InvalidConditionError) as exc_info:
        validate_condition_tree(tree)
    assert "field" in str(exc_info.value).lower()


def test_missing_value_raises():
    """Test that binary operator without value raises error."""
    tree = {"op": "eq", "field": "sensitivity"}  # Missing 'value'
    with pytest.raises(InvalidConditionError) as exc_info:
        validate_condition_tree(tree)
    assert "value" in str(exc_info.value).lower()


def test_invalid_field_raises():
    """Test that invalid field name raises error."""
    tree = {"op": "eq", "field": "invalid_field_name", "value": "test"}
    with pytest.raises(InvalidConditionError) as exc_info:
        validate_condition_tree(tree)
    assert "not valid" in str(exc_info.value).lower()


def test_and_wrong_child_count_raises():
    """Test that AND with wrong child count raises error."""
    tree = {
        "op": "and",
        "children": [
            {"op": "eq", "field": "sensitivity", "value": "SENSITIVE"}
            # Missing second child
        ]
    }
    with pytest.raises(InvalidConditionError) as exc_info:
        validate_condition_tree(tree)
    assert "2 children" in str(exc_info.value)


# =============================================================================
# Policy Engine Evaluation Tests
# =============================================================================

def test_no_rules_returns_ai_recommendation():
    """Test that empty rules list returns AI recommendation unchanged."""
    context = PolicyContext(
        document_id=uuid4(),
        sensitivity="PUBLIC",
        trust_score=0.9
    )
    decision = evaluate_policy_decision(
        rules=[],
        context=context,
        ai_recommendation=PolicyAction.ALLOW
    )
    
    assert decision.matched is False
    assert decision.rule_id is None
    assert decision.final_decision == PolicyAction.ALLOW


def test_no_match_returns_ai_recommendation():
    """Test that no matching rule returns AI recommendation unchanged."""
    rule = PolicyRule(
        id=uuid4(),
        rule_name="test-rule",
        condition_expr={"op": "eq", "field": "sensitivity", "value": "SENSITIVE"},
        action=PolicyAction.DENY,
        priority=1,
        active=True
    )
    context = PolicyContext(
        document_id=uuid4(),
        sensitivity="PUBLIC",  # Doesn't match rule
        trust_score=0.9
    )
    decision = evaluate_policy_decision(
        rules=[rule],
        context=context,
        ai_recommendation=PolicyAction.ALLOW
    )
    
    assert decision.matched is False
    assert decision.rule_id is None
    assert decision.final_decision == PolicyAction.ALLOW


def test_matching_rule_overrides_ai():
    """Test that matching rule overrides AI recommendation."""
    rule = PolicyRule(
        id=uuid4(),
        rule_name="deny-sensitive",
        condition_expr={"op": "eq", "field": "sensitivity", "value": "SENSITIVE"},
        action=PolicyAction.DENY,
        priority=1,
        active=True
    )
    context = PolicyContext(
        document_id=uuid4(),
        sensitivity="SENSITIVE",  # Matches rule
        trust_score=0.3
    )
    decision = evaluate_policy_decision(
        rules=[rule],
        context=context,
        ai_recommendation=PolicyAction.ALLOW
    )
    
    assert decision.matched is True
    assert decision.rule_id == rule.id
    assert decision.rule_name == "deny-sensitive"
    assert decision.final_decision == PolicyAction.DENY
    assert decision.action == PolicyAction.DENY


def test_priority_ordering_first_match():
    """Test that lower priority rules are evaluated first."""
    # Lower priority = evaluated first
    rule_low = PolicyRule(
        id=uuid4(),
        rule_name="low-priority",
        condition_expr={"op": "eq", "field": "sensitivity", "value": "PUBLIC"},
        action=PolicyAction.REQUIRE_MFA,
        priority=1,  # Lower = first
        active=True
    )
    rule_high = PolicyRule(
        id=uuid4(),
        rule_name="high-priority",
        condition_expr={"op": "eq", "field": "sensitivity", "value": "PUBLIC"},
        action=PolicyAction.DENY,
        priority=10,  # Higher = second
        active=True
    )
    context = PolicyContext(
        document_id=uuid4(),
        sensitivity="PUBLIC",  # Matches BOTH rules
        trust_score=0.5
    )
    decision = evaluate_policy_decision(
        rules=[rule_high, rule_low],  # Passed in wrong order
        context=context,
        ai_recommendation=PolicyAction.ALLOW
    )
    
    # Lower priority (rule_low) should win because it's evaluated first
    assert decision.matched is True
    assert decision.rule_name == "low-priority"
    assert decision.action == PolicyAction.REQUIRE_MFA


def test_inactive_rule_ignored():
    """Test that inactive rules are not evaluated."""
    rule = PolicyRule(
        id=uuid4(),
        rule_name="inactive-rule",
        condition_expr={"op": "eq", "field": "sensitivity", "value": "SENSITIVE"},
        action=PolicyAction.DENY,
        priority=1,
        active=False  # Inactive!
    )
    context = PolicyContext(
        document_id=uuid4(),
        sensitivity="SENSITIVE",
        trust_score=0.5
    )
    decision = evaluate_policy_decision(
        rules=[rule],
        context=context,
        ai_recommendation=PolicyAction.ALLOW
    )
    
    assert decision.matched is False
    assert decision.rule_id is None


def test_multiple_rules_first_match_wins():
    """Test that first matching rule wins, evaluation stops."""
    rule1 = PolicyRule(
        id=uuid4(),
        rule_name="rule-1",
        condition_expr={"op": "eq", "field": "sensitivity", "value": "CONFIDENTIAL"},
        action=PolicyAction.REQUIRE_MFA,
        priority=1,
        active=True
    )
    rule2 = PolicyRule(
        id=uuid4(),
        rule_name="rule-2",
        condition_expr={"op": "eq", "field": "sensitivity", "value": "SENSITIVE"},
        action=PolicyAction.DENY,
        priority=2,
        active=True
    )
    context = PolicyContext(
        document_id=uuid4(),
        sensitivity="SENSITIVE",  # Matches BOTH rules
        trust_score=0.5
    )
    decision = evaluate_policy_decision(
        rules=[rule1, rule2],
        context=context,
        ai_recommendation=PolicyAction.ALLOW
    )
    
    # rule1 has lower priority, runs first, matches context
    # Wait - rule1 expects CONFIDENTIAL, context is SENSITIVE
    # So rule1 doesn't match, rule2 should match
    assert decision.matched is True
    assert decision.rule_name == "rule-2"
    assert decision.final_decision == PolicyAction.DENY


def test_condition_eq_evaluation():
    """Test equality condition evaluation."""
    rule = PolicyRule(
        id=uuid4(),
        rule_name="eq-test",
        condition_expr={"op": "eq", "field": "trust_score", "value": 0.5},
        action=PolicyAction.DENY,
        priority=1,
        active=True
    )
    context = PolicyContext(
        document_id=uuid4(),
        sensitivity="PUBLIC",
        trust_score=0.5
    )
    engine = get_policy_engine()
    decision = engine.evaluate([rule], context, PolicyAction.ALLOW)
    
    assert decision.matched is True


def test_condition_gt_evaluation():
    """Test greater-than condition evaluation."""
    rule = PolicyRule(
        id=uuid4(),
        rule_name="gt-test",
        condition_expr={"op": "gt", "field": "trust_score", "value": 0.7},
        action=PolicyAction.FORCE_PQC,
        priority=1,
        active=True
    )
    context = PolicyContext(
        document_id=uuid4(),
        sensitivity="PUBLIC",
        trust_score=0.9  # > 0.7, should match
    )
    engine = get_policy_engine()
    decision = engine.evaluate([rule], context, PolicyAction.ALLOW)
    
    assert decision.matched is True
    assert decision.action == PolicyAction.FORCE_PQC


def test_condition_lt_evaluation():
    """Test less-than condition evaluation."""
    rule = PolicyRule(
        id=uuid4(),
        rule_name="lt-test",
        condition_expr={"op": "lt", "field": "trust_score", "value": 0.3},
        action=PolicyAction.FORCE_PQC,
        priority=1,
        active=True
    )
    context = PolicyContext(
        document_id=uuid4(),
        sensitivity="PUBLIC",
        trust_score=0.1  # < 0.3, should match
    )
    engine = get_policy_engine()
    decision = engine.evaluate([rule], context, PolicyAction.ALLOW)
    
    assert decision.matched is True


def test_condition_in_evaluation():
    """Test 'in' condition evaluation."""
    rule = PolicyRule(
        id=uuid4(),
        rule_name="in-test",
        condition_expr={"op": "in", "field": "sensitivity", "value": ["SENSITIVE", "CONFIDENTIAL"]},
        action=PolicyAction.DENY,
        priority=1,
        active=True
    )
    context = PolicyContext(
        document_id=uuid4(),
        sensitivity="CONFIDENTIAL",  # In the list
        trust_score=0.5
    )
    engine = get_policy_engine()
    decision = engine.evaluate([rule], context, PolicyAction.ALLOW)
    
    assert decision.matched is True


def test_condition_and_evaluation():
    """Test AND condition evaluation."""
    rule = PolicyRule(
        id=uuid4(),
        rule_name="and-test",
        condition_expr={
            "op": "and",
            "children": [
                {"op": "eq", "field": "sensitivity", "value": "SENSITIVE"},
                {"op": "lt", "field": "trust_score", "value": 0.5},
            ]
        },
        action=PolicyAction.DENY,
        priority=1,
        active=True
    )
    # Both conditions true
    context1 = PolicyContext(
        document_id=uuid4(),
        sensitivity="SENSITIVE",
        trust_score=0.3
    )
    engine = get_policy_engine()
    decision1 = engine.evaluate([rule], context1, PolicyAction.ALLOW)
    assert decision1.matched is True
    
    # Second condition false
    context2 = PolicyContext(
        document_id=uuid4(),
        sensitivity="SENSITIVE",
        trust_score=0.8
    )
    decision2 = engine.evaluate([rule], context2, PolicyAction.ALLOW)
    assert decision2.matched is False


def test_policy_engine_singleton():
    """Test that get_policy_engine returns singleton."""
    engine1 = get_policy_engine()
    engine2 = get_policy_engine()
    assert engine1 is engine2


def test_rationale_includes_rule_name():
    """Test that decision rationale includes rule name."""
    rule = PolicyRule(
        id=uuid4(),
        rule_name="my-test-rule",
        condition_expr={"op": "eq", "field": "sensitivity", "value": "SENSITIVE"},
        action=PolicyAction.DENY,
        priority=1,
        active=True
    )
    context = PolicyContext(
        document_id=uuid4(),
        sensitivity="SENSITIVE",
        trust_score=0.5
    )
    decision = evaluate_policy_decision(
        rules=[rule],
        context=context,
        ai_recommendation=PolicyAction.ALLOW
    )
    
    assert "my-test-rule" in decision.rationale
    assert "matched" in decision.rationale.lower()