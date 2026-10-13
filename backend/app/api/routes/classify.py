"""Sensitivity classification endpoint, ``SPEC.md`` 3.2, ``PRD.md`` FR-1."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.deps import ClassifyCaller, DbSession, resolve_seeded_actor
from app.classifier import classify
from app.classifier.schemas import ClassificationRequest, ClassificationResponse
from app.db.enums import AuditEventType
from app.db.repositories import audit as audit_repo
from app.db.repositories import classification as classification_repo
from app.db.repositories import documents as documents_repo
from app.event_bus import EventType, schedule_publish

router = APIRouter(tags=["classifier"])


@router.post(
    "/classify",
    response_model=ClassificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Classify a document's sensitivity",
)
def classify_document(
    request: ClassificationRequest,
    session: DbSession,
    caller: ClassifyCaller,
) -> ClassificationResponse:
    """Classify a document, persist the result, and record it in the audit log.

    The classification row, the audit entry, and the document's status change all
    share the request's transaction. That is the requirement, not an optimisation:
    ``PRD.md`` Section 7 treats a decision with no corresponding audit entry as a
    defect, so a committed classification that lost its log entry to a partial
    failure would itself be the defect.

    Note what the classifier is and is not: the label and confidence come from
    the active engine — the trained model when an artifact is configured, else
    the keyword engine (``SPEC.md`` 3.2). The fail-safe escalation that low
    confidence triggers is real in both, and is not a stub. Each result records
    its own ``model_version`` so the persisted row names the engine that produced
    it.

    Raises:
        HTTPException: 404 if the document is not registered. Classifying an
            unknown id would either violate the foreign key or, worse, invent a
            document row from a classification request.
    """
    document = documents_repo.get_document(session, request.document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_unknown_document_detail(request.document_id),
        )

    actor = resolve_seeded_actor(session, caller)
    result = classify(request.content)

    row = classification_repo.append_classification(
        session, document_id=document.id, result=result
    )
    audit_repo.append_entry(
        session,
        event_type=AuditEventType.CLASSIFICATION_COMPLETED.value,
        document_id=document.id,
        actor_id=actor.id,
        payload=classification_repo.classification_audit_payload(
            document_id=document.id,
            result=result,
            classification_id=row.id,
        ),
    )
    documents_repo.mark_classified(session, document)

    schedule_publish(
        session,
        EventType.DOCUMENT_CLASSIFIED,
        {
            "document_id": str(document.id),
            "classification_id": str(row.id),
            "sensitivity_label": result.sensitivity_label.value,
        },
    )

    return ClassificationResponse.from_result(
        document_id=document.id,
        result=result,
        # The persisted timestamp, not a fresh datetime.now(). The two would
        # differ by microseconds, which is enough for the value an auditor reads
        # in the response to disagree with the row it describes.
        classified_at=row.classified_at,
    )


def _unknown_document_detail(document_id: UUID) -> str:
    """Explain a 404 in terms of the action the caller needs to take."""
    return (
        f"No document registered with id {document_id}. Register it first via "
        "POST /api/v1/documents."
    )
