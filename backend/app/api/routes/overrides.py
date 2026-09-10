"""Manual classification override, ``PRD.md`` FR-12."""

from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.deps import DbSession, OverrideCaller, resolve_seeded_actor
from app.classifier.override_schemas import (
    ManualOverrideRequest,
    ManualOverrideResponse,
)
from app.db.enums import AuditEventType
from app.db.repositories import audit as audit_repo
from app.db.repositories import documents as documents_repo
from app.db.repositories import overrides as override_repo

router = APIRouter(tags=["overrides"])


@router.post(
    "/manual-overrides",
    response_model=ManualOverrideResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Override a document's effective sensitivity label",
)
def create_manual_override(
    request: ManualOverrideRequest,
    session: DbSession,
    caller: OverrideCaller,
) -> ManualOverrideResponse:
    """Persist one override and the matching audit entry.

    ``original_label`` is the current effective sensitivity: the latest
    override's ``new_label``, or the latest classification if none exists.
    The client cannot supply it. A later classification does not change that
    snapshot after this row is written. This handler does not change
    ``documents.current_status``.

    FR-12's confirmation checkbox is enforced in the frontend. It is not an
    API field: a client-supplied boolean is not evidence the analyst confirmed.

    Raises:
        HTTPException: 404 if the document is unknown, 422 if it has not been
            classified or ``new_label`` equals the current effective label.
    """
    document = documents_repo.get_document(session, request.document_id)
    if document is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=_unknown_document_detail(request.document_id),
        )

    effective = override_repo.effective_for_document(session, document.id)
    if effective is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "No classification recorded for this document. Classify it "
                "first via POST /api/v1/classify."
            ),
        )
    if request.new_label == effective.label:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=(
                "new_label must differ from the current effective label "
                f"({effective.label.value})."
            ),
        )

    actor = resolve_seeded_actor(session, caller)
    row = override_repo.append_override(
        session,
        document_id=document.id,
        overridden_by=actor.id,
        original_label=effective.label,
        new_label=request.new_label,
        justification=request.justification,
    )
    audit_repo.append_entry(
        session,
        event_type=AuditEventType.MANUAL_OVERRIDE.value,
        document_id=document.id,
        actor_id=actor.id,
        payload=override_repo.override_audit_payload(row=row),
    )
    return ManualOverrideResponse(
        id=row.id,
        document_id=row.document_id,
        overridden_by=row.overridden_by,
        original_label=row.original_label,
        new_label=row.new_label,
        justification=row.justification,
        overridden_at=row.overridden_at,
    )


def _unknown_document_detail(document_id: UUID) -> str:
    """Explain a 404 in terms of the action the caller needs to take."""
    return (
        f"No document registered with id {document_id}. Register it first via "
        "POST /api/v1/documents."
    )
