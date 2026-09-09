"""Append to ``risk_scores``, ``SPEC.md`` 3.3, ``PRD.md`` FR-2.

Append only. There is no update function.
"""

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import RiskScore
from app.risk_engine.scorer import RiskScoreResult


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
