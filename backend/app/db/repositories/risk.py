"""Append to ``risk_scores``, ``SPEC.md`` 3.3, ``PRD.md`` FR-2.

Append only. There is no update function.
"""

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import RiskScore
from app.risk_engine.scorer import RiskScoreResult


def get_risk_score(session: Session, risk_score_id: UUID) -> RiskScore | None:
    """Return one contextual risk row, or ``None`` if it was never written."""
    return session.scalars(
        select(RiskScore).where(RiskScore.id == risk_score_id)
    ).one_or_none()


def latest_for_document(session: Session, document_id: UUID) -> RiskScore | None:
    """Return the most recent contextual score for a document, if any.

    Ordered by ``computed_at`` then ``id``. Same tiebreak as classification:
    two rows in one transaction share a timestamp and still need an order.
    """
    return session.scalars(
        select(RiskScore)
        .where(RiskScore.document_id == document_id)
        .order_by(RiskScore.computed_at.desc(), RiskScore.id.desc())
        .limit(1)
    ).one_or_none()


def append_risk_score(
    session: Session,
    *,
    document_id: UUID,
    result: RiskScoreResult,
) -> RiskScore:
    """Record one contextual scoring and return the row, without committing.

    ``risk_value`` is already a ``Decimal`` quantized to four places; it is not
    converted through ``float``.
    """
    row = RiskScore(
        document_id=document_id,
        risk_value=result.risk_value,
        model_version=result.model_version,
        context_snapshot=result.snapshot.as_json(),
    )
    session.add(row)
    session.flush()
    return row


def risk_score_audit_payload(
    *,
    document_id: UUID,
    result: RiskScoreResult,
    risk_score_id: UUID,
) -> dict[str, Any]:
    """Audit payload for one contextual scoring.

    JSON primitives only. Includes ``model_version`` so a stored score remains
    attributable after the weights change.
    """
    payload: dict[str, Any] = {
        "risk_score_id": str(risk_score_id),
        "document_id": str(document_id),
        "risk_value": str(result.risk_value),
        "model_version": result.model_version,
    }
    payload.update(result.snapshot.as_json())
    return payload
