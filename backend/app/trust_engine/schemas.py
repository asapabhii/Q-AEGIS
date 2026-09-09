"""Pydantic models for the trust-score API, ``SPEC.md`` 3.5.

No raw dicts cross this boundary. ``consensus_value`` is computed by the
engine; the client cannot supply it. Extra keys are forbidden. The five
outputs are caller-asserted until 3.4 exists to produce them.
"""

from datetime import datetime
import math
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.db.enums import AgentType
from app.db.models.risk import EXPECTED_AGENT_COUNT
from app.trust_engine.consensus import AgentScore, TrustScoreResult

MAX_RATIONALE_CHARS = 4000


class AgentOutputBody(BaseModel):
    """One caller-supplied agent score. ``PRD.md`` FR-3 requires a rationale."""

    model_config = ConfigDict(extra="forbid")

    agent_type: AgentType
    score: Decimal = Field(ge=0, le=1)
    rationale: str = Field(min_length=1, max_length=MAX_RATIONALE_CHARS)

    @field_validator("score", mode="before")
    @classmethod
    def score_must_be_a_real_number(cls, value: object) -> object:
        """Booleans are ints in Python; rejecting them avoids True meaning 1."""
        if isinstance(value, bool):
            raise ValueError("must be a finite number")
        if isinstance(value, float) and not math.isfinite(value):
            raise ValueError("must be a finite number")
        if isinstance(value, Decimal) and not value.is_finite():
            raise ValueError("must be a finite number")
        return value

    @field_validator("score")
    @classmethod
    def score_must_be_finite_decimal(cls, value: Decimal) -> Decimal:
        """JSON has no NaN; a Decimal or string still can. Reject those too."""
        if not value.is_finite():
            raise ValueError("must be a finite number")
        return value

    @field_validator("rationale")
    @classmethod
    def rationale_must_not_be_blank(cls, value: str) -> str:
        """Whitespace-only is not a rationale."""
        if not value.strip():
            raise ValueError("rationale must contain non-whitespace characters")
        return value.strip()

    def as_score(self) -> AgentScore:
        """Project into the consensus function's input type."""
        return AgentScore(
            agent_type=self.agent_type,
            score=self.score,
            rationale=self.rationale,
        )


class TrustScoreRequest(BaseModel):
    """Evaluate consensus for one persisted contextual risk row."""

    model_config = ConfigDict(extra="forbid")

    risk_score_id: UUID
    outputs: list[AgentOutputBody] = Field(
        min_length=EXPECTED_AGENT_COUNT,
        max_length=EXPECTED_AGENT_COUNT,
    )

    @model_validator(mode="after")
    def outputs_must_be_the_five_types(self) -> "TrustScoreRequest":
        """A duplicate or a missing type is 422, not a silently short mean."""
        types = [item.agent_type for item in self.outputs]
        seen = set(types)
        if len(seen) != len(types):
            duplicates = sorted({item.value for item in types if types.count(item) > 1})
            raise ValueError(
                "Exactly one output is required for each agent type. "
                f"Duplicate: {', '.join(duplicates)}."
            )
        missing = [agent.value for agent in AgentType if agent not in seen]
        if missing:
            raise ValueError(
                "Exactly one output is required for each agent type. "
                f"Missing: {', '.join(missing)}."
            )
        return self

    def scores(self) -> list[AgentScore]:
        """The five outputs as the consensus function expects them."""
        return [item.as_score() for item in self.outputs]


class AgentOutputResponse(BaseModel):
    """One persisted agent output."""

    id: UUID
    agent_type: AgentType
    score: Decimal
    rationale: str


class TrustScoreResponse(BaseModel):
    """One persisted consensus pass."""

    id: UUID
    document_id: UUID
    risk_score_id: UUID
    consensus_value: Decimal
    consensus_version: str
    outputs: list[AgentOutputResponse]
    computed_at: datetime

    @classmethod
    def from_row(
        cls,
        *,
        trust_score_id: UUID,
        document_id: UUID,
        risk_score_id: UUID,
        result: TrustScoreResult,
        output_ids: list[UUID],
        computed_at: datetime,
    ) -> "TrustScoreResponse":
        """Build a response from the persisted rows and the consensus result."""
        return cls(
            id=trust_score_id,
            document_id=document_id,
            risk_score_id=risk_score_id,
            consensus_value=result.consensus_value,
            consensus_version=result.consensus_version,
            outputs=[
                AgentOutputResponse(
                    id=output_id,
                    agent_type=item.agent_type,
                    score=item.score,
                    rationale=item.rationale,
                )
                for output_id, item in zip(output_ids, result.outputs, strict=True)
            ],
            computed_at=computed_at,
        )
