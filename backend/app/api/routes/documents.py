"""Document registration, ``SPEC.md`` Section 5.

PARTIAL IMPLEMENTATION OF ``PRD.md`` FR-1's INPUT PATH, and labelled as such
because the gap matters to anyone building on it: this registers a document's
metadata, it does not accept a file. There is no object storage in this build, so
``storage_path`` stays null and ``current_status`` stays ``registered`` rather
than ``uploaded``.

It exists because ``classification_metadata.document_id`` is a foreign key to
``documents.id``, so a classification cannot be recorded for a document the
system has never heard of. The alternative was to leave ``/classify`` accepting
any invented UUID, which is what it did before the schema existed.

The file-upload half belongs to the classification request screen (``SPEC.md``
3.13, Input Screen 1) and its 50 MB / PDF-DOCX-XLSX-TXT validation rules. When it
lands, this endpoint gains a ``storage_path`` and this docstring loses its first
paragraph.
"""

from datetime import datetime
from uuid import UUID

from fastapi import APIRouter, status
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.api.deps import DbSession, RegisterDocumentCaller, resolve_seeded_actor
from app.db.enums import AuditEventType, DocumentStatus
from app.db.repositories import audit as audit_repo
from app.db.repositories import documents as documents_repo

router = APIRouter(tags=["documents"])

#: Upper bound on a filename, matching ``documents.filename``'s ``varchar(255)``.
MAX_FILENAME_CHARS = 255


class DocumentRegistrationRequest(BaseModel):
    """A request to register one document's metadata."""

    model_config = ConfigDict(extra="forbid")

    filename: str = Field(
        min_length=1,
        max_length=MAX_FILENAME_CHARS,
        description="Original filename, not a storage key.",
    )

    @field_validator("filename")
    @classmethod
    def filename_must_not_be_blank(cls, value: str) -> str:
        """Reject a whitespace-only filename.

        ``min_length`` alone accepts a single space, which would store a document
        with no usable name and no error anywhere.
        """
        if not value.strip():
            raise ValueError(
                "filename must contain at least one non-whitespace character"
            )
        return value


class DocumentResponse(BaseModel):
    """A registered document."""

    id: UUID
    filename: str
    storage_path: str | None
    current_status: DocumentStatus
    uploaded_by: UUID
    uploaded_at: datetime


@router.post(
    "/documents",
    response_model=DocumentResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a document's metadata (no file upload, see module docstring)",
)
def register_document(
    request: DocumentRegistrationRequest,
    session: DbSession,
    caller: RegisterDocumentCaller,
) -> DocumentResponse:
    """Register a document and record the registration in the audit log.

    Both writes share the request's transaction, so a document row cannot exist
    without the audit entry that accounts for it (``PRD.md`` Section 7: a decision
    with no corresponding audit entry is a defect).
    """
    actor = resolve_seeded_actor(session, caller)
    document = documents_repo.register_document(
        session, uploaded_by=actor.id, filename=request.filename
    )

    audit_repo.append_entry(
        session,
        event_type=AuditEventType.DOCUMENT_REGISTERED.value,
        document_id=document.id,
        actor_id=actor.id,
        payload={
            "document_id": str(document.id),
            "filename": document.filename,
            "storage_path": document.storage_path,
            "current_status": document.current_status.value,
            "registered_by": str(actor.id),
            "registered_by_role": actor.role.value,
        },
    )

    return DocumentResponse(
        id=document.id,
        filename=document.filename,
        storage_path=document.storage_path,
        current_status=document.current_status,
        uploaded_by=document.uploaded_by,
        uploaded_at=document.uploaded_at,
    )
