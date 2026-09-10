"""Read and write ``documents``."""

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

    ``current_status`` starts at :attr:`~app.db.enums.DocumentStatus.REGISTERED`
    when no ``storage_path`` is given, because a document whose file has not been
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
    """Advance a document's lifecycle pointer to ``CLASSIFIED``.

    This is an UPDATE, and it is the one kind the schema permits: ``documents`` is
    not a history table and ``current_status`` is a pointer to the current stage,
    not a decision record. The decision itself is a new ``classification_metadata``
    row plus an ``audit_log`` entry, both of which outlive any later status change,
    so moving the pointer discards nothing.

    Idempotent for an already-classified document, and deliberately not a
    backwards transition: a document that has reached ``PROTECTED`` or
    ``ARCHIVED`` is left alone rather than being dragged back to ``CLASSIFIED`` by
    a reclassification.
    """
    if document.current_status in (
        DocumentStatus.REGISTERED,
        DocumentStatus.UPLOADED,
    ):
        document.current_status = DocumentStatus.CLASSIFIED
        session.flush()
    return document


def list_documents(session: Session) -> list[Document]:
    """Every document, newest ``uploaded_at`` first, then ``id``.

    No caller limit. FR-14 is the whole monitored set. Pagination is later,
    when volume makes an unbounded read a real problem.
    """
    return list(
        session.scalars(
            select(Document).order_by(Document.uploaded_at.desc(), Document.id.desc())
        ).all()
    )


def get_document(
    session: Session, document_id: UUID, *, for_update: bool = False
) -> Document | None:
    """Return one document, or ``None`` if no such row exists.

    Returns ``None`` rather than raising so the caller decides what absence means.
    The API layer turns it into a 404; a background consumer might reasonably
    treat it as an event arriving out of order.

    ``for_update`` takes a row lock for the rest of the transaction. Override
    writes use it so two concurrent relabels cannot snapshot the same
    predecessor. Released on commit or rollback.
    """
    statement = select(Document).where(Document.id == document_id)
    if for_update:
        statement = statement.with_for_update()
    return session.scalars(statement).one_or_none()
