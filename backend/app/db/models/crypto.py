"""``crypto_profiles``, ``document_ciphertexts``, and ``migration_schedule``.

``SPEC.md`` 3.7 and 3.10.
"""

from datetime import date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, ForeignKey, LargeBinary, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, created_timestamp, jsonb_column, uuid_primary_key
from app.db.enums import CryptoProfileType, MigrationStatus
from app.db.types import CRYPTO_PROFILE_TYPE, MIGRATION_STATUS


class CryptoProfile(Base):
    """The protection profile selected for a document. APPEND-ONLY.

    ``PRD.md`` FR-6 requires every selection to reference the specific trust score
    that drove it, which is ``trust_score_id``, and requires reselection when the
    underlying score changes materially, which is why this is a history table
    rather than a column on ``documents``.

    The parameter sets behind each profile are in ``SPEC.md`` Section 6 and are
    not restated here. Note for anyone reading this while implementing 3.7:
    liboqs is not independently audited, so nothing built on top of this column
    should be described as audited-grade or FIPS-certified.
    """

    __tablename__ = "crypto_profiles"

    id: Mapped[UUID] = uuid_primary_key()
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    trust_score_id: Mapped[UUID] = mapped_column(
        ForeignKey("trust_scores.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    profile_type: Mapped[CryptoProfileType] = mapped_column(
        CRYPTO_PROFILE_TYPE, nullable=False
    )
    selected_at: Mapped[datetime] = created_timestamp(index=True)


class DocumentCiphertext(Base):
    """Encrypted document bytes plus a master-key-wrapped DEK for shredding.

    ``PRD.md`` FR-8 destroys keys, not audit rows. Storing ``wrapped_dek`` here
    lets shredding delete or overwrite that column later while ciphertext and
    audit history remain.

    SECURITY CAVEAT: liboqs is not independently audited; hybrid and
    post-quantum rows depend on it when those profiles are used.
    """

    __tablename__ = "document_ciphertexts"

    id: Mapped[UUID] = uuid_primary_key()
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    crypto_profile_id: Mapped[UUID] = mapped_column(
        ForeignKey("crypto_profiles.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    ciphertext: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    nonce: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    wrapped_dek: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    kem_ciphertext: Mapped[bytes | None] = mapped_column(LargeBinary, nullable=True)
    algorithm: Mapped[str] = mapped_column(String(80), nullable=False)
    created_at: Mapped[datetime] = created_timestamp(index=True)


class MigrationSchedule(Base):
    """A document's place in the post-quantum upgrade queue, ``PRD.md`` FR-9."""

    __tablename__ = "migration_schedule"
    __table_args__ = (
        CheckConstraint("priority_rank > 0", name="priority_rank_positive"),
    )

    id: Mapped[UUID] = uuid_primary_key()
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    priority_rank: Mapped[int] = mapped_column(nullable=False)
    scheduled_upgrade_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    status: Mapped[MigrationStatus] = mapped_column(MIGRATION_STATUS, nullable=False)
    # FR-9 requires ranking output to include the constraint values that produced
    # it, not just the resulting order, so the rank is reproducible after the
    # fact. Without this a rank is an assertion nobody can re-derive.
    constraint_snapshot: Mapped[dict[str, Any]] = jsonb_column()
