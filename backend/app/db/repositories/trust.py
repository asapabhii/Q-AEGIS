"""Append ``agent_outputs`` and ``trust_scores``, ``SPEC.md`` 3.5.

Append only. There is no update function for either table.
"""

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import AgentOutput, TrustScore
from app.trust_engine.consensus import WEIGHTS, AgentScore, TrustScoreResult


def get_trust_score(session: Session, trust_score_id: UUID) -> TrustScore | None:
    """Return one consensus row, or ``None`` if it was never written."""
    return session.scalars(
        select(TrustScore).where(TrustScore.id == trust_score_id)
    ).one_or_none()


def append_agent_outputs(
    session: Session,
    *,
    risk_score_id: UUID,
    outputs: tuple[AgentScore, ...],
) -> list[AgentOutput]:
    """Insert the five outputs in consensus order and return them.

    Does not commit. A duplicate ``(risk_score_id, agent_type)`` is a unique
    violation for the caller to map to 409.
    """
    rows: list[AgentOutput] = []
    for item in outputs:
        row = AgentOutput(
            risk_score_id=risk_score_id,
            agent_type=item.agent_type,
            score=item.score,
            rationale=item.rationale,
        )
        session.add(row)
        rows.append(row)
    session.flush()
    return rows


def append_trust_score(
    session: Session,
    *,
    document_id: UUID,
    risk_score_id: UUID,
    result: TrustScoreResult,
) -> TrustScore:
    """Record one consensus pass and return the row, without committing."""
    row = TrustScore(
        document_id=document_id,
        risk_score_id=risk_score_id,
        consensus_value=result.consensus_value,
        consensus_version=result.consensus_version,
    )
    session.add(row)
    session.flush()
    return row


def trust_score_audit_payload(
    *,
    document_id: UUID,
    risk_score_id: UUID,
    result: TrustScoreResult,
    trust_score_id: UUID,
    output_ids: list[UUID],
) -> dict[str, Any]:
    """Audit payload for one consensus pass. JSON primitives only.

    Includes the weights and the agent-output ids so the stored number remains
    attributable after the formula changes.
    """
    return {
        "trust_score_id": str(trust_score_id),
        "document_id": str(document_id),
        "risk_score_id": str(risk_score_id),
        "consensus_value": str(result.consensus_value),
        "consensus_version": result.consensus_version,
        "agent_output_ids": [str(item) for item in output_ids],
        "weights": {agent.value: str(weight) for agent, weight in WEIGHTS.items()},
    }
