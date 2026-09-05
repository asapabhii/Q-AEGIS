"""``documents``, the root of every decision the system records."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, created_timestamp, uuid_primary_key
from app.db.enums import DocumentStatus
from app.db.types import DOCUMENT_STATUS


class Document(Base):
    """A document under the system's protection.

    ``current_status`` is the only mutable status field in the schema. It is a
    pointer to the current lifecycle stage, not a decision record: every decision
    that moves it is preserved in its own append-only history table and in
    ``audit_log``, so overwriting the pointer loses nothing.
    """

    __tablename__ = "documents"

    id: Mapped[UUID] = uuid_primary_key()
    uploaded_by: Mapped[UUID] = mapped_column(
        # RESTRICT, not CASCADE: deleting a user must not silently take their
        # documents, and through them a chain of decisions and audit entries,
        # with it. A deletion that would orphan a document should fail and be
        # dealt with deliberately.
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    storage_path: Mapped[str | None] = mapped_column(
        String(500),
        # Null while a document is REGISTERED: its metadata row exists but no
        # file has been stored, because this build has no object storage. Not
        # null once a file is actually written.
        nullable=True,
    )
    uploaded_at: Mapped[datetime] = created_timestamp()
    current_status: Mapped[DocumentStatus] = mapped_column(
        DOCUMENT_STATUS,
        nullable=False,
        default=DocumentStatus.REGISTERED,
    )
