"""Contextual risk scoring endpoint, ``SPEC.md`` 3.3, ``PRD.md`` FR-2."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.deps import DbSession, RiskScoreCaller, resolve_seeded_actor
from app.db.enums import AuditEventType
from app.db.repositories import audit as audit_repo
from app.db.repositories import documents as documents_repo
from app.db.repositories import risk as risk_repo
from app.risk_engine.schemas import RiskScoreRequest, RiskScoreResponse
from app.risk_engine.scorer import score

router = APIRouter(tags=["risk"])


@router.post(
    "/risk-scores",
    response_model=RiskScoreResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Compute contextual risk for a registered document",
)
def compute_risk_score(
    request: RiskScoreRequest,
    session: DbSession,
    caller: RiskScoreCaller,
) -> RiskScoreResponse:
    """Score a complete snapshot, persist the row, and write the audit entry.

    The risk row and the audit entry share the request transaction. ``PRD.md``
    Section 7 treats a decision with no audit entry as a defect.

    ``risk_value`` is computed here. It is not accepted from the client.

    Raises:
        HTTPException: 404 if the document is not registered.
    """
    document = documents_repo.get_document(session, request.document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_unknown_document_detail(request.document_id),
        )

    actor = resolve_seeded_actor(session, caller)
    result = score(request.snapshot())
    row = risk_repo.append_risk_score(session, document_id=document.id, result=result)
    audit_repo.append_entry(
        session,
        event_type=AuditEventType.RISK_SCORE_COMPUTED.value,
        document_id=document.id,
        actor_id=actor.id,
        payload=risk_repo.risk_score_audit_payload(
            document_id=document.id,
            result=result,
            risk_score_id=row.id,
        ),
    )
    return RiskScoreResponse.from_row(
        risk_score_id=row.id,
        document_id=document.id,
        result=result,
        computed_at=row.computed_at,
    )


def _unknown_document_detail(document_id: UUID) -> str:
    """Explain a 404 in terms of the action the caller needs to take."""
    return (
        f"No document registered with id {document_id}. Register it first via "
        "POST /api/v1/documents."
    )
