"""``audit_log``, ``SPEC.md`` 3.8, ``PRD.md`` FR-7.

Every decision anywhere in the pipeline writes exactly one row here. The pure
Merkle functions that produce ``merkle_root_at_time`` live in
:mod:`app.audit.merkle` and take no database handle, deliberately: an auditor
must be able to re-verify with exported entries and a root obtained
independently.
"""

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CHAR, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, created_timestamp, jsonb_column, uuid_primary_key

#: Length of a hex-encoded SHA-256 digest.
HASH_HEX_LENGTH = 64


class AuditLog(Base):
    """One immutable record of one decision.

    APPEND-ONLY against UPDATE, DELETE, and TRUNCATE, enforced by database
    triggers installed in the initial migration. ``AGENTS.md`` is explicit that no
    UPDATE or DELETE may be written against this table in application code or in a
    migration, and that the triggers are not to be worked around.

    Chains are per document. ``prev_hash`` refers to the previous entry for the
    same ``document_id``; rows with a null ``document_id`` form one separate
    system chain. Verification and the audit viewer (``PRD.md`` FR-15) both operate
    on a single document's chain, and one global chain would serialise every write
    in the system behind a single row.

    Honest limit, because this is exactly the kind of guarantee that gets
    overstated: ``prev_hash`` links rows but is not itself covered by
    ``payload_hash``, so someone with write access could recompute an internally
    consistent chain. ``merkle_root_at_time``, and external anchoring of that
    root, are what make that detectable. The chain alone is not sufficient and
    must not be described as if it were.
    """

    __tablename__ = "audit_log"
    __table_args__ = (
        # A fork is two rows claiming the same predecessor, so this rejects one
        # outright. NULLS NOT DISTINCT extends the guarantee to the genesis
        # entry: without it Postgres treats every null prev_hash as unique and a
        # chain could have two beginnings.
        UniqueConstraint(
            "document_id",
            "prev_hash",
            name="no_forked_chain",
            postgresql_nulls_not_distinct=True,
        ),
    )

    id: Mapped[UUID] = uuid_primary_key()
    document_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="RESTRICT"),
        # Nullable for events with no document, for example a policy rule being
        # created. Such rows form the system chain described above.
        nullable=True,
        index=True,
    )
    actor_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        # Nullable for events raised by a system module with no human actor, such
        # as a scheduled risk recomputation.
        nullable=True,
        index=True,
    )
    # varchar, not an enum: every module in SPEC.md Section 3 adds event types as
    # it lands, and gating each behind a migration would make the audit log the
    # thing that slows down writing to the audit log. The write-side vocabulary
    # is app.db.enums.AuditEventType.
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    # The canonical event body that payload_hash is the hash of. Storing it is
    # what makes independent re-verification possible at all: a hash with no
    # payload can only be checked against other hashes, never against the facts
    # it claims to commit to. See docs/data-dictionary.md, deviation 1.
    payload: Mapped[dict[str, Any]] = jsonb_column()
    payload_hash: Mapped[str] = mapped_column(CHAR(HASH_HEX_LENGTH), nullable=False)
    prev_hash: Mapped[str | None] = mapped_column(
        CHAR(HASH_HEX_LENGTH),
        # Null on the genesis entry, which by definition has no predecessor. A
        # sentinel of 64 zeros was rejected: it is indistinguishable from a real
        # hash, and it invites verification code that accepts a forged all-zero
        # value as proof of "this is the start of the chain".
        nullable=True,
    )
    merkle_root_at_time: Mapped[str] = mapped_column(
        CHAR(HASH_HEX_LENGTH), nullable=False
    )
    created_at: Mapped[datetime] = created_timestamp(index=True)
