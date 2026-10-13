"""``risk_scores``, ``agent_outputs``, ``trust_scores``, ``SPEC.md`` 3.3 to 3.5."""

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, created_timestamp, jsonb_column, uuid_primary_key
from app.db.enums import AgentType
from app.db.types import AGENT_TYPE

#: Number of agents expected to score one assessment, ``PRD.md`` FR-3.
#:
#: Deliberately not a database constraint. A partial set is a legitimate
#: intermediate state while the five agents are still running, and rejecting it at
#: insert time would make the first agent's write fail. The consumer is what must
#: refuse to compute a consensus from fewer than five (``SPEC.md`` 3.5).
EXPECTED_AGENT_COUNT = 5


class RiskScore(Base):
    """One contextual risk computation. APPEND-ONLY.

    ``PRD.md`` FR-2: risk recomputes on a schedule and on trigger events, each
    computation records the signals that contributed to it, and a new computation
    never overwrites a prior one. A database trigger rejects UPDATE.

    ``risk_value`` is this engine's own score (``SPEC.md`` 3.3), not the
    five-agent aggregate. That aggregate is ``trust_scores.consensus_value``.
    """

    __tablename__ = "risk_scores"
    __table_args__ = (
        CheckConstraint("risk_value >= 0 AND risk_value <= 1", name="risk_value_range"),
    )

    id: Mapped[UUID] = uuid_primary_key()
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # numeric(5,4), not (4,3): the scorer rounds to four decimal places, and
    # three would store a different number than the API returned. Same reason
    # as classification_metadata.confidence_score.
    risk_value: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    # 64, not 30: kept in step with classification_metadata.model_version. The
    # current "contextual-risk-additive-0.1.0" is exactly 30 chars, so any longer
    # scorer version would overflow the old width. See that column's note.
    model_version: Mapped[str] = mapped_column(String(64), nullable=False)
    context_snapshot: Mapped[dict[str, Any]] = jsonb_column()
    computed_at: Mapped[datetime] = created_timestamp(index=True)


class AgentOutput(Base):
    """One agent's score and rationale for one risk assessment.

    A child table rather than five nullable columns on ``risk_scores``, so a sixth
    agent type needs no migration and the one-to-five relationship is structural
    rather than conventional.

    ``rationale`` is not nullable: ``PRD.md`` FR-3 requires every agent output to
    carry a human-readable rationale alongside its number, and an agent that
    cannot explain itself has not produced a usable output.
    """

    __tablename__ = "agent_outputs"
    __table_args__ = (
        CheckConstraint("score >= 0 AND score <= 1", name="score_range"),
        # One output per agent per assessment. A duplicate means an agent ran
        # twice and the consensus function would double-count it.
        UniqueConstraint("risk_score_id", "agent_type", name="one_output_per_agent"),
    )

    id: Mapped[UUID] = uuid_primary_key()
    risk_score_id: Mapped[UUID] = mapped_column(
        ForeignKey("risk_scores.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    agent_type: Mapped[AgentType] = mapped_column(AGENT_TYPE, nullable=False)
    score: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    rationale: Mapped[str] = mapped_column(Text, nullable=False)


class TrustScore(Base):
    """One consensus trust score. APPEND-ONLY.

    ``PRD.md`` FR-4 requires every trust score to reference the exact agent
    outputs that produced it and the consensus function to be versioned, which is
    what ``risk_score_id`` and ``consensus_version`` are for: the agent outputs are
    reachable through the assessment, and the version identifies the function that
    combined them. A stored number with no traceable derivation is the thing FR-4
    exists to prevent.
    """

    __tablename__ = "trust_scores"
    __table_args__ = (
        CheckConstraint(
            "consensus_value >= 0 AND consensus_value <= 1",
            name="consensus_value_range",
        ),
    )

    id: Mapped[UUID] = uuid_primary_key()
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    risk_score_id: Mapped[UUID] = mapped_column(
        ForeignKey("risk_scores.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    consensus_value: Mapped[Decimal] = mapped_column(Numeric(4, 3), nullable=False)
    consensus_version: Mapped[str] = mapped_column(String(30), nullable=False)
    computed_at: Mapped[datetime] = created_timestamp(index=True)
