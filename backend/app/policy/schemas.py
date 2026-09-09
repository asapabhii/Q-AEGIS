"""Pydantic models for the policy API, ``SPEC.md`` 3.6.

No raw dicts cross this boundary. ``final_decision`` and ``overridden`` are
computed by the engine; the client cannot supply them. Extra keys are forbidden.
"""

from datetime import datetime
import math
from typing import Any
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.classifier.labels import SensitivityLabel
from app.db.enums import PolicyAction
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
    """Evaluate the gate for one registered document."""

    model_config = ConfigDict(extra="forbid")

    document_id: UUID
    ai_recommendation: PolicyAction
    sensitivity_label: SensitivityLabel
    risk_value: float = Field(ge=0.0, le=1.0)
    trust_score: float = Field(ge=0.0, le=1.0)

    @field_validator("risk_value", "trust_score", mode="before")
    @classmethod
    def scores_must_be_real_numbers(cls, value: object) -> object:
        """Booleans are ints in Python; rejecting them avoids True meaning 1.0."""
        if isinstance(value, bool):
            raise ValueError("must be a finite number")
        if isinstance(value, (int, float)) and not math.isfinite(value):
            raise ValueError("must be a finite number")
        return value

    def facts(self) -> DocumentFacts:
        """Closed evaluation snapshot, excluding ``document_id``."""
        return DocumentFacts(
            sensitivity_label=self.sensitivity_label.value,
            risk_value=self.risk_value,
            trust_score=self.trust_score,
            ai_recommendation=self.ai_recommendation,
        )


class PolicyDecisionResponse(BaseModel):
    """One persisted pass through the gate."""

    id: UUID
    document_id: UUID
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
        result: PolicyEvalResult,
        decided_at: datetime,
    ) -> "PolicyDecisionResponse":
        """Build a response from the persisted row and the engine result."""
        return cls(
            id=decision_id,
            document_id=document_id,
            rule_id=result.rule_id,
            rule_name=result.rule_name,
            ai_recommendation=result.ai_recommendation,
            final_decision=result.final_decision,
            overridden=result.overridden,
            policy_version=result.policy_version,
            decided_at=decided_at,
        )
