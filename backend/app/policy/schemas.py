"""Pydantic models for the policy API, ``SPEC.md`` 3.6.

No raw dicts cross this boundary. ``final_decision`` and ``overridden`` are
computed by the engine; the client cannot supply them. Extra keys are forbidden.

``sensitivity_label``, ``risk_value``, and ``trust_score`` are read from
persisted rows. The client cannot supply them. ``ai_recommendation`` is still
caller-asserted until 3.4 exists to produce it.
"""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.classifier.labels import SensitivityLabel
from app.db.enums import PolicyAction
from app.db.models import ClassificationMetadata, RiskScore, TrustScore
from app.policy.conditions import condition_as_json, parse_condition
from app.policy.engine import DocumentFacts, PolicyEvalResult

MAX_RULE_NAME_CHARS = 150


class PolicyRuleCreateRequest(BaseModel):
    """Author one override rule. ``PRD.md`` FR-13."""

    model_config = ConfigDict(extra="forbid")

    rule_name: str = Field(min_length=1, max_length=MAX_RULE_NAME_CHARS)
    condition_expr: dict[str, Any]
    action: PolicyAction
    priority: int = Field(gt=0)

    @field_validator("rule_name")
    @classmethod
    def rule_name_must_not_be_blank(cls, value: str) -> str:
        """Whitespace-only is not a unique name."""
        if not value.strip():
            raise ValueError("rule_name must contain non-whitespace characters")
        return value.strip()

    @field_validator("condition_expr")
    @classmethod
    def condition_must_be_v1_tree(cls, value: dict[str, Any]) -> dict[str, Any]:
        """Reject unknown operators/fields before the row is stored."""
        return condition_as_json(parse_condition(value))


class PolicyRuleResponse(BaseModel):
    """One stored rule."""

    id: UUID
    rule_name: str
    condition_expr: dict[str, Any]
    action: PolicyAction
    priority: int
    active: bool
    created_at: datetime


class PolicyDecisionRequest(BaseModel):
    """Evaluate the gate from one persisted trust-score row.

    ``document_id`` is taken from that row. The client cannot supply the
    label, the risk value, or the trust score.
    """

    model_config = ConfigDict(extra="forbid")

    trust_score_id: UUID
    ai_recommendation: PolicyAction


class PolicyDecisionResponse(BaseModel):
    """One persisted pass through the gate, including the facts that were used."""

    id: UUID
    document_id: UUID
    trust_score_id: UUID
    risk_score_id: UUID
    classification_id: UUID
    sensitivity_label: SensitivityLabel
    risk_value: Decimal
    trust_score: Decimal
    rule_id: UUID | None
    rule_name: str | None
    ai_recommendation: PolicyAction
    final_decision: PolicyAction
    overridden: bool
    policy_version: str
    decided_at: datetime

    @classmethod
    def from_row(
        cls,
        *,
        decision_id: UUID,
        document_id: UUID,
        trust_score_id: UUID,
        risk_score_id: UUID,
        classification_id: UUID,
        facts: DocumentFacts,
        result: PolicyEvalResult,
        decided_at: datetime,
        risk_value: Decimal,
        trust_score: Decimal,
    ) -> "PolicyDecisionResponse":
        """Build a response from the persisted rows and the engine result."""
        return cls(
            id=decision_id,
            document_id=document_id,
            trust_score_id=trust_score_id,
            risk_score_id=risk_score_id,
            classification_id=classification_id,
            sensitivity_label=SensitivityLabel(facts.sensitivity_label),
            risk_value=risk_value,
            trust_score=trust_score,
            rule_id=result.rule_id,
            rule_name=result.rule_name,
            ai_recommendation=result.ai_recommendation,
            final_decision=result.final_decision,
            overridden=result.overridden,
            policy_version=result.policy_version,
            decided_at=decided_at,
        )


def facts_from_persisted(
    *,
    classification: ClassificationMetadata,
    risk: RiskScore,
    trust: TrustScore,
    ai_recommendation: PolicyAction,
) -> DocumentFacts:
    """Closed evaluation snapshot from stored rows, not from the client."""
    return DocumentFacts(
        sensitivity_label=classification.sensitivity_label.value,
        risk_value=float(Decimal(str(risk.risk_value))),
        trust_score=float(Decimal(str(trust.consensus_value))),
        ai_recommendation=ai_recommendation,
    )
