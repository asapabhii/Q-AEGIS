"""Persistence for PQ-signed audit checkpoints, ``SPEC.md`` 3.8, ``PRD.md`` FR-7.

The side-effecting half of checkpoint anchoring. The pure signing and
verification live in :mod:`app.audit.checkpoint`; the orchestration that loads a
chain, recomputes its root, unwraps the signing secret, and calls both lives in
:mod:`app.audit.service`. This module only reads and writes the two tables.

Like :mod:`app.db.repositories.audit`, writes here flush rather than commit: a
checkpoint is issued inside the caller's transaction so it commits with whatever
else that unit of work is doing, or not at all.

There is no update and no delete function, and none may be added. Both tables
reject UPDATE, DELETE, and TRUNCATE at the database level.
"""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models.checkpoint import AuditCheckpoint, AuditSigningKey


def get_active_signing_key(session: Session) -> AuditSigningKey | None:
    """Return the current signing key, or ``None`` if none has been created yet.

    The active key is the most recently created row: rotation is an INSERT of a
    new key, never a mutation of a flag, which is what keeps the table
    append-only. ``id`` breaks a tie between two keys sharing a transaction
    timestamp so the choice is deterministic.
    """
    statement = (
        select(AuditSigningKey)
        .order_by(AuditSigningKey.created_at.desc(), AuditSigningKey.id.desc())
        .limit(1)
    )
    return session.scalars(statement).first()


def get_signing_key(session: Session, key_id: UUID) -> AuditSigningKey | None:
    """Return one signing key by id, or ``None`` if it does not exist.

    Used when verifying a stored checkpoint: verification uses the key that
    actually signed it, which may be a superseded key rather than the active one.
    """
    return session.get(AuditSigningKey, key_id)


def insert_signing_key(
    session: Session,
    *,
    algorithm: str,
    public_key: str,
    wrapped_secret_key: bytes,
) -> AuditSigningKey:
    """Persist a new signing key and return it, flushed but not committed.

    Args:
        session: Active session, inside a transaction.
        algorithm: liboqs mechanism name, e.g. ``"ML-DSA-87"``.
        public_key: Hex-encoded raw public key (published for pinning).
        wrapped_secret_key: The secret key already wrapped under the master key.

    Returns:
        The pending :class:`AuditSigningKey` row with its ``id`` populated.
    """
    key = AuditSigningKey(
        algorithm=algorithm,
        public_key=public_key,
        wrapped_secret_key=wrapped_secret_key,
    )
    session.add(key)
    session.flush()
    return key


def insert_checkpoint(
    session: Session,
    *,
    document_id: UUID | None,
    signing_key_id: UUID,
    tree_size: int,
    merkle_root: str,
    signature: str,
    signed_at: datetime,
) -> AuditCheckpoint:
    """Persist a Signed Tree Head and return it, flushed but not committed.

    Args:
        session: Active session, inside a transaction.
        document_id: Chain the checkpoint commits to, or ``None`` for the system
            chain.
        signing_key_id: The key that produced ``signature``.
        tree_size: Number of leaves the root covers.
        merkle_root: Hex Merkle root over the prefix ``0..tree_size-1``.
        signature: Hex-encoded ML-DSA-87 signature over the canonical bytes.
        signed_at: Issue time; this exact value is part of the signed bytes.

    Returns:
        The pending :class:`AuditCheckpoint` row with its ``id`` populated.
    """
    checkpoint = AuditCheckpoint(
        document_id=document_id,
        signing_key_id=signing_key_id,
        tree_size=tree_size,
        merkle_root=merkle_root,
        signature=signature,
        signed_at=signed_at,
    )
    session.add(checkpoint)
    session.flush()
    return checkpoint


def get_checkpoint(session: Session, checkpoint_id: UUID) -> AuditCheckpoint | None:
    """Return one checkpoint by id, or ``None`` if it does not exist."""
    return session.get(AuditCheckpoint, checkpoint_id)


def list_checkpoints(
    session: Session, document_id: UUID | None
) -> list[AuditCheckpoint]:
    """Return one chain's checkpoints, oldest prefix first.

    Ordered by ``tree_size`` then ``signed_at`` so the sequence reads as the
    chain grew. The system chain (``document_id`` is ``None``) is selected with
    an ``IS NULL`` test, matching the chain queries in
    :mod:`app.db.repositories.audit`.
    """
    statement = select(AuditCheckpoint)
    if document_id is None:
        statement = statement.where(AuditCheckpoint.document_id.is_(None))
    else:
        statement = statement.where(AuditCheckpoint.document_id == document_id)
    statement = statement.order_by(
        AuditCheckpoint.tree_size.asc(), AuditCheckpoint.signed_at.asc()
    )
    return list(session.scalars(statement).all())
