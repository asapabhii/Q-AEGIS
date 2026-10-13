"""Contextual risk scoring endpoint, ``SPEC.md`` 3.3, ``PRD.md`` FR-2."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status
from sqlalchemy.orm import Session

from app.api.deps import DbSession, RiskScoreCaller, resolve_seeded_actor
from app.db.enums import AuditEventType
from app.db.models import Document, User
from app.db.repositories import audit as audit_repo
from app.db.repositories import documents as documents_repo
from app.db.repositories import identity as identity_repo
from app.db.repositories import risk as risk_repo
from app.event_bus import EventType, schedule_publish
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

    The subject of the access (``actor_user_id``) is validated to resolve to a
    registered user before the score is attributed to it, so a report cannot
    name a subject that does not exist. The authenticated reporter is recorded
    distinctly from the subject on the audit entry (``actor_id``) and, for a
    self-describing record, echoed into the audit payload as ``reported_by_*``;
    for third-party reporting the reporter and the subject differ.

    Raises:
        HTTPException: 404 if the document is not registered, or if
            ``actor_user_id`` does not resolve to a registered user.
    """
    document, _subject = _load_document_and_subject(session, request)

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
            reported_by_user_id=actor.id,
            reported_by_role=actor.role.value,
        ),
    )
    return RiskScoreResponse.from_row(
        risk_score_id=row.id,
        document_id=document.id,
        result=result,
        computed_at=row.computed_at,
    )


@router.post(
    "/risk-triggers",
    response_model=RiskScoreResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Publish a risk trigger and recompute immediately",
)
def trigger_risk_recompute(
    request: RiskScoreRequest,
    session: DbSession,
    caller: RiskScoreCaller,
) -> RiskScoreResponse:
    """FR-2 immediate recompute on new-device / after-hours style events.

    Queues ``risk.trigger`` for after-commit publish on the Redis Streams bus
    (validated no-op when Redis is unset), then scores and persists the same
    way as ``POST /risk-scores``.
    """
    # Validate the document and the subject identity *before* publishing, so a
    # trigger event is never emitted for an unregistered document or a subject
    # that does not resolve to a real user. compute_risk_score re-validates
    # (defence in depth: it is also reachable directly).
    _load_document_and_subject(session, request)

    # Publish the *server-derived* snapshot facts, never raw request fields:
    # after_hours is computed here, so a consumer that recomputes off the bus
    # sees the same value the synchronous score used, not a client assertion.
    snapshot = request.snapshot()
    schedule_publish(
        session,
        EventType.RISK_TRIGGER,
        {
            "document_id": str(request.document_id),
            "actor_user_id": str(request.actor_user_id),
            "device_id": request.device_id,
            "device_is_new": request.device_is_new,
            "after_hours": snapshot.after_hours,
            "org_timezone": snapshot.org_timezone,
            "accessed_at": request.accessed_at.isoformat(),
        },
    )
    return compute_risk_score(request, session, caller)


def _load_document_and_subject(
    session: Session, request: RiskScoreRequest
) -> tuple[Document, User]:
    """Return the registered document and the resolved subject user.

    Both the document and the subject identity asserted by the request are
    checked here, the document first so an unknown-document 404 keeps its
    existing wording. A subject that does not resolve to a registered user is a
    404: a report may only be filed against a principal the system knows.
    """
    document = documents_repo.get_document(session, request.document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_unknown_document_detail(request.document_id),
        )
    subject = identity_repo.get_by_id(session, request.actor_user_id)
    if subject is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_unknown_subject_detail(request.actor_user_id),
        )
    return document, subject


def _unknown_document_detail(document_id: UUID) -> str:
    """Explain a 404 in terms of the action the caller needs to take."""
    return (
        f"No document registered with id {document_id}. Register it first via "
        "POST /api/v1/documents."
    )


def _unknown_subject_detail(actor_user_id: UUID) -> str:
    """Explain a 404 for a subject that does not resolve to a known user."""
    return (
        f"actor_user_id {actor_user_id} does not resolve to a registered user. "
        "The subject of a contextual-risk report must be a known principal."
    )
