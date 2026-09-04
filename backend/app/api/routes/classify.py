"""Classification endpoint, ``SPEC.md`` 3.2's ``POST /classify`` contract.

Backed by the keyword-rule STUB in :mod:`app.classifier.stub_classifier`. The
API contract here is the real one and is not expected to change when the stub is
replaced by the real model, apart from ``content`` dropping out of the request
once a document store exists to resolve ``document_id`` against.
"""

from datetime import datetime, timezone

from fastapi import APIRouter, status

from app.api.deps import ClassifyCaller
from app.classifier.schemas import ClassificationRequest, ClassificationResponse
from app.classifier.stub_classifier import classify

router = APIRouter(tags=["classifier"])


@router.post(
    "/classify",
    response_model=ClassificationResponse,
    status_code=status.HTTP_200_OK,
    summary="Classify a document's sensitivity (stub implementation)",
)
def classify_document(
    request: ClassificationRequest,
    caller: ClassifyCaller,
) -> ClassificationResponse:
    """Classify one document and return its label, confidence, and provenance.

    A confidence score below the configured threshold escalates the returned
    label to the more sensitive option and sets ``is_defaulted`` to True, per
    ``PRD.md`` FR-1. Clients must treat ``is_defaulted`` as a prompt for analyst
    review, not as an error.

    NOT YET IMPLEMENTED, and required before this endpoint is complete against
    ``PRD.md``: persisting the result to ``classification_metadata`` as a new
    append-only row (FR-1, never overwriting a prior classification) and writing
    a corresponding ``audit_log`` entry (FR-7). Until the database layer exists,
    this endpoint computes and returns a classification without recording it. A
    decision with no audit entry is a defect per ``PRD.md`` Section 7, so this
    endpoint is not finished, only usable.

    Args:
        request: The document reference and, for Phase 1 only, its inline text.
        caller: Resolved caller role, injected by the authorization guard. The
            guard runs before this body executes; an unauthorized caller never
            reaches this code.

    Returns:
        The classification result.
    """
    result = classify(request.content)
    return ClassificationResponse.from_result(
        document_id=request.document_id,
        result=result,
        classified_at=datetime.now(timezone.utc),
    )
