"""Read and write `documents`."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.enums import DocumentStatus
from app.db.models import Document


def register_document(
    session: Session,
    *,
    uploaded_by: UUID,
    filename: str,
    storage_path: str | None = None,
) -> Document:
    """Create a document row and return it, without committing.

    `current_status` starts at :attr:~app.db.enums.DocumentStatus.REGISTERED
    when no `storage_path` is given, because a document whose file has not been
    stored is not uploaded and the lifecycle field should not claim otherwise.
    """
    document = Document(
        uploaded_by=uploaded_by,
        filename=filename,
        storage_path=storage_path,
        current_status=(
            DocumentStatus.UPLOADED if storage_path else DocumentStatus.REGISTERED
        ),
    )
    session.add(document)
    session.flush()
    return document


def mark_classified(session: Session, document: Document) -> Document:
    """Advance a document's lifecycle pointer to `CLASSIFIED`.

    This is an UPDATE, and it is the one kind the schema permits: `documents` is
    not a history table and `current_status` is a pointer to the current stage,
    not a decision record. The decision itself is a new `classification_metadata`
    row plus an `audit_log` entry, both of which outlive any later status change,
    so moving the pointer discards nothing.

    Idempotent for an already-classified document, and deliberately not a
    backwards transition: a document that has reached `PROTECTED` or
    `ARCHIVED` is left alone rather than being dragged back to `CLASSIFIED` by
    a reclassification.
    """
    if document.current_status in (
        DocumentStatus.REGISTERED,
        DocumentStatus.UPLOADED,
    ):
        document.current_status = DocumentStatus.CLASSIFIED
        session.flush()
    return document


def update_status(session: Session, document_id: UUID, new_status: DocumentStatus) -> Document:
    """Update a document's current status.
    
    Args:
        session: Active database session.
        document_id: UUID of the document to update.
        new_status: The new status to set.
        
    Returns:
        The updated document.
        
    Raises:
        ValueError: If the document doesn't exist.
    """
    document = get_document(session, document_id)
    if document is None:
        raise ValueError(f"Document {document_id} not found")
    document.current_status = new_status
    session.flush()
    return document


def get_document(session: Session, document_id: UUID) -> Document | None:
    """Return one document, or `None` if no such row exists.

    Returns `None` rather than raising so the caller decides what absence means.
    The API layer turns it into a 404; a background consumer might reasonably
    treat it as an event arriving out of order.
    """
    return session.scalars(
        select(Document).where(Document.id == document_id)
    ).one_or_none()