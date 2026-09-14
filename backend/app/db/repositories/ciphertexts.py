"""Persist encrypted document payloads, ``SPEC.md`` 3.7.

SECURITY CAVEAT: liboqs is NOT independently audited.
"""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crypto.schemas import EncryptResult
from app.db.models import DocumentCiphertext


def append_ciphertext(
    session: Session,
    *,
    document_id: UUID,
    crypto_profile_id: UUID,
    result: EncryptResult,
) -> DocumentCiphertext:
    """Store one ciphertext row. Does not commit.

    SECURITY CAVEAT: liboqs is NOT independently audited.
    """
    row = DocumentCiphertext(
        document_id=document_id,
        crypto_profile_id=crypto_profile_id,
        ciphertext=result.ciphertext,
        nonce=result.nonce,
        wrapped_dek=result.wrapped_dek,
        kem_ciphertext=result.kem_ciphertext,
        algorithm=result.algorithm,
    )
    session.add(row)
    session.flush()
    return row


def latest_for_document(
    session: Session, document_id: UUID
) -> DocumentCiphertext | None:
    """Most recent ciphertext for a document, if any.

    SECURITY CAVEAT: liboqs is NOT independently audited.
    """
    return session.scalars(
        select(DocumentCiphertext)
        .where(DocumentCiphertext.document_id == document_id)
        .order_by(DocumentCiphertext.created_at.desc(), DocumentCiphertext.id.desc())
        .limit(1)
    ).one_or_none()


def list_for_document(
    session: Session, document_id: UUID, *, for_update: bool = False
) -> list[DocumentCiphertext]:
    """All ciphertext rows for a document, oldest first.

    ``for_update`` locks the matching rows for the rest of the transaction
    (used by crypto-shredding so concurrent inserts wait on the document lock
    plus these rows).

    SECURITY CAVEAT: liboqs is NOT independently audited.
    """
    statement = (
        select(DocumentCiphertext)
        .where(DocumentCiphertext.document_id == document_id)
        .order_by(DocumentCiphertext.created_at.asc(), DocumentCiphertext.id.asc())
    )
    if for_update:
        statement = statement.with_for_update()
    return list(session.scalars(statement).all())
