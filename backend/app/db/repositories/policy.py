"""Read ``policy_rules`` and append ``policy_decisions``, ``SPEC.md`` 3.6.

``policy_rules`` is mutable (a rule can be deactivated later). ``policy_decisions``
is a history of evaluations; there is no update function for it.
"""

from typing import Any
from uuid import UUID

from sqlalchemy import exists, select
from sqlalchemy.orm import Session

from app.db.enums import PolicyAction
from app.db.models import PolicyDecision, PolicyRule
from app.policy.engine import EvaluableRule, PolicyEvalResult


def insert_rule(
    session: Session,
    *,
    rule_name: str,
    condition_expr: dict[str, Any],
    action: PolicyAction,
    priority: int,
    created_by: UUID,
) -> PolicyRule:
    """Insert one active rule and return it, without committing."""
    row = PolicyRule(
        rule_name=rule_name,
        condition_expr=condition_expr,
        action=action,
        priority=priority,
        active=True,
        created_by=created_by,
    )
    session.add(row)
    session.flush()
    return row


def list_active_rules(session: Session) -> list[PolicyRule]:
    """Active rules in evaluation order: lower ``priority`` first, then ``id``."""
    return list(
        session.scalars(
            select(PolicyRule)
            .where(PolicyRule.active.is_(True))
            .order_by(PolicyRule.priority.asc(), PolicyRule.id.asc())
        ).all()
    )


def as_evaluable(row: PolicyRule) -> EvaluableRule:
    """Project a stored row into the engine's input type."""
    return EvaluableRule(
        id=row.id,
        rule_name=row.rule_name,
        action=row.action,
        condition=dict(row.condition_expr),
    )


def append_decision(
    session: Session,
    *,
    document_id: UUID,
    result: PolicyEvalResult,
) -> PolicyDecision:
    """Record one gate evaluation and return the row, without committing."""
    row = PolicyDecision(
        document_id=document_id,
        rule_id=result.rule_id,
        ai_recommendation=result.ai_recommendation,
        final_decision=result.final_decision,
        overridden=result.overridden,
    )
    session.add(row)
    session.flush()
    return row


def document_has_policy_decision(session: Session, document_id: UUID) -> bool:
    """True when at least one gate evaluation exists for this document.

    FR-6 selects protection after the policy gate. v1 enforces that by requiring
    a ``policy_decisions`` row for the same ``document_id``, not by re-running
    the evaluator here. A ``deny`` still counts: the gate already recorded.
    """
    return bool(
        session.scalar(
            select(exists().where(PolicyDecision.document_id == document_id))
        )
    )


def rule_created_audit_payload(*, rule: PolicyRule) -> dict[str, Any]:
    """Audit payload for authoring a rule. JSON primitives only."""
    return {
        "rule_id": str(rule.id),
        "rule_name": rule.rule_name,
        "action": rule.action.value,
        "priority": rule.priority,
        "active": rule.active,
        "condition_expr": rule.condition_expr,
    }


def decision_audit_payload(
    *,
    document_id: UUID,
    result: PolicyEvalResult,
    decision_id: UUID,
    facts: dict[str, str | float],
    trust_score_id: UUID,
    risk_score_id: UUID,
    classification_id: UUID,
) -> dict[str, Any]:
    """Audit payload for one gate evaluation. JSON primitives only.

    Source row ids stay in the payload so the floats on the fact snapshot
    remain attributable after a later reclassify or rescore.
    """
    payload: dict[str, Any] = {
        "policy_decision_id": str(decision_id),
        "document_id": str(document_id),
        "trust_score_id": str(trust_score_id),
        "risk_score_id": str(risk_score_id),
        "classification_id": str(classification_id),
        "rule_id": str(result.rule_id) if result.rule_id is not None else None,
        "rule_name": result.rule_name,
        "ai_recommendation": result.ai_recommendation.value,
        "final_decision": result.final_decision.value,
        "overridden": result.overridden,
        "policy_version": result.policy_version,
    }
    payload.update(facts)
    return payload
