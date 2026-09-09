"""Trust-score consensus endpoint, ``SPEC.md`` 3.5, ``PRD.md`` FR-4."""

from uuid import UUID

import psycopg
from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import IntegrityError

from app.api.deps import DbSession, TrustScoreCaller, resolve_seeded_actor
from app.db.enums import AuditEventType
from app.db.repositories import audit as audit_repo
from app.db.repositories import risk as risk_repo
from app.db.repositories import trust as trust_repo
from app.trust_engine.consensus import IncompleteAgentSetError, combine
from app.trust_engine.schemas import TrustScoreRequest, TrustScoreResponse

router = APIRouter(tags=["trust"])


@router.post(
    "/trust-scores",
    response_model=TrustScoreResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Compute the five-agent trust consensus for one risk score",
)
def compute_trust_score(
    request: TrustScoreRequest,
    session: DbSession,
    caller: TrustScoreCaller,
) -> TrustScoreResponse:
    """Persist the five outputs, the consensus row, and the audit entry.

    ``consensus_value`` is computed here. It is not accepted from the client.
    The five scores are caller-asserted until 3.4 exists to produce them.

    Raises:
        HTTPException: 404 if the risk score is unknown, 422 if the agent set
            is incomplete, 409 if this risk score already has outputs.
    """
    risk_row = risk_repo.get_risk_score(session, request.risk_score_id)
    if risk_row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_unknown_risk_score_detail(request.risk_score_id),
        )

    actor = resolve_seeded_actor(session, caller)
    try:
        result = combine(request.scores())
    except IncompleteAgentSetError as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=str(exc),
        ) from exc

    try:
        output_rows = trust_repo.append_agent_outputs(
            session, risk_score_id=risk_row.id, outputs=result.outputs
        )
    except IntegrityError as exc:
        _raise_output_conflict(exc)

    row = trust_repo.append_trust_score(
        session,
        document_id=risk_row.document_id,
        risk_score_id=risk_row.id,
        result=result,
    )
    output_ids = [item.id for item in output_rows]
    audit_repo.append_entry(
        session,
        event_type=AuditEventType.TRUST_SCORE_UPDATED.value,
        document_id=risk_row.document_id,
        actor_id=actor.id,
        payload=trust_repo.trust_score_audit_payload(
            document_id=risk_row.document_id,
            risk_score_id=risk_row.id,
            result=result,
            trust_score_id=row.id,
            output_ids=output_ids,
        ),
    )
    return TrustScoreResponse.from_row(
        trust_score_id=row.id,
        document_id=risk_row.document_id,
        risk_score_id=risk_row.id,
        result=result,
        output_ids=output_ids,
        computed_at=row.computed_at,
    )


def _raise_output_conflict(exc: IntegrityError) -> None:
    """Map a duplicate agent set onto 409, not 500."""
    orig = exc.orig
    if isinstance(orig, psycopg.errors.UniqueViolation):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "This risk score already has agent outputs. Consensus is "
                "append-only: score a new contextual risk row first."
            ),
        ) from exc
    raise exc


def _unknown_risk_score_detail(risk_score_id: UUID) -> str:
    """Explain a 404 in terms of the action the caller needs to take."""
    return (
        f"No risk score with id {risk_score_id}. Compute one first via "
        "POST /api/v1/risk-scores."
    )
