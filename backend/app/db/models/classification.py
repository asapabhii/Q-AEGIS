"""``classification_metadata`` and ``manual_overrides``, ``SPEC.md`` 3.2."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, created_timestamp, uuid_primary_key
from app.db.enums import SensitivityLabel
from app.db.types import SENSITIVITY_LABEL

#: Minimum override justification length, ``PRD.md`` FR-12.
#:
#: Enforced in the database as well as in the API. It is an acceptance criterion,
#: not a UI nicety, and a row violating it should not be storable by any path,
#: including a migration or a direct SQL insert.
MIN_JUSTIFICATION_CHARS = 20


class ClassificationMetadata(Base):
    """One classification run's result. APPEND-ONLY.

    A document is reclassified over its lifetime and every prior classification
    stays readable (``PRD.md`` FR-1: prior classifications are never overwritten,
    only superseded). A database trigger rejects UPDATE on this table, and there
    is deliberately no update path in the repository layer either.

    The classifier also produces a pre-escalation ``base_label``, the threshold in
    force, the keywords that fired, and a rationale. Those are not columns here:
    the first two are derivable and the last two are artifacts of the current
    keyword stub that ``SPEC.md`` 3.2 replaces with a trained model. All four are
    preserved in the matching ``audit_log.payload``, so nothing is lost and this
    table does not accumulate columns tied to an implementation with a scheduled
    end.
    """

    __tablename__ = "classification_metadata"
    __table_args__ = (
        CheckConstraint(
            "confidence_score >= 0 AND confidence_score <= 1",
            name="confidence_score_range",
        ),
    )

    id: Mapped[UUID] = uuid_primary_key()
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    sensitivity_label: Mapped[SensitivityLabel] = mapped_column(
        SENSITIVITY_LABEL, nullable=False
    )
    # numeric(5,4), not (4,3): the classifier rounds confidence to four decimal
    # places, and three would store a different number than the API returned for
    # the same classification. See docs/data-dictionary.md, deviation 5.
    confidence_score: Mapped[Decimal] = mapped_column(Numeric(5, 4), nullable=False)
    model_version: Mapped[str] = mapped_column(String(30), nullable=False)
    is_defaulted: Mapped[bool] = mapped_column(nullable=False)
    classified_at: Mapped[datetime] = created_timestamp(index=True)


class ManualOverride(Base):
    """A human overriding an AI classification, ``PRD.md`` FR-12."""

    __tablename__ = "manual_overrides"
    __table_args__ = (
        CheckConstraint(
            f"char_length(justification) >= {MIN_JUSTIFICATION_CHARS}",
            name="justification_min_length",
        ),
        CheckConstraint("new_label <> original_label", name="label_actually_changed"),
    )

    id: Mapped[UUID] = uuid_primary_key()
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    overridden_by: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    original_label: Mapped[SensitivityLabel] = mapped_column(
        SENSITIVITY_LABEL, nullable=False
    )
    new_label: Mapped[SensitivityLabel] = mapped_column(
        SENSITIVITY_LABEL, nullable=False
    )
    justification: Mapped[str] = mapped_column(Text, nullable=False)
    overridden_at: Mapped[datetime] = created_timestamp()
