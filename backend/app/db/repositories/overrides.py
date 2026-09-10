"""Read and append ``manual_overrides``, ``PRD.md`` FR-12.

Append only. There is no update or clear function. A later classification
does not retract a human override; only another override changes the
effective label. That rule is the product contract, not an implementation
shortcut: the gate must not let the stub classifier silently undo an analyst.
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.classifier.labels import SensitivityLabel, SensitivitySource
from app.db.models import ClassificationMetadata, Document, ManualOverride
from app.db.repositories import classification as classification_repo
from app.db.repositories import documents as documents_repo


@dataclass(frozen=True)
class EffectiveSensitivity:
    """The label every downstream decision must treat as current."""

    label: SensitivityLabel
    classification: ClassificationMetadata
    override: ManualOverride | None

    @property
    def source(self) -> SensitivitySource:
        """``manual_override`` if one exists, otherwise ``classification``."""
        if self.override is not None:
            return SensitivitySource.MANUAL_OVERRIDE
        return SensitivitySource.CLASSIFICATION

    @property
    def override_id(self) -> UUID | None:
        """The override row that supplied the label, if any."""
        if self.override is None:
            return None
        return self.override.id


def lock_document(session: Session, document_id: UUID) -> Document | None:
    """Lock the document row for the rest of this transaction.

    Override writes take this before reading the effective label and hold it
    through the insert and the audit append. The second writer waits, then
    sees the first commit, so ``original_label`` is the previous effective
    label rather than a stale classification. Released on commit or rollback.
    """
    return documents_repo.get_document(session, document_id, for_update=True)


def latest_for_document(session: Session, document_id: UUID) -> ManualOverride | None:
    """Return the most recent override for a document, if any.

    Ordered by ``overridden_at`` then ``id``. Writers stamp ``overridden_at``
    with ``clock_timestamp()`` after taking :func:`lock_document`, so the
    clock time is the insert time under the lock, not the transaction start.
    ``id`` is only a last-resort tiebreak.
    """
    return session.scalars(
        select(ManualOverride)
        .where(ManualOverride.document_id == document_id)
        .order_by(
            ManualOverride.overridden_at.desc(),
            ManualOverride.id.desc(),
        )
        .limit(1)
    ).one_or_none()


def effective_for_document(
    session: Session, document_id: UUID
) -> EffectiveSensitivity | None:
    """Resolve the effective label, or ``None`` when nothing has been classified.

    An override without a classification cannot happen through the API. If a
    test inserts one anyway, this still returns ``None``: FR-12 overrides an
    AI classification, and inventing a label from the override alone would
    hide that the AI record is missing.
    """
    classification = classification_repo.latest_for_document(session, document_id)
    if classification is None:
        return None
    override = latest_for_document(session, document_id)
    if override is None:
        return EffectiveSensitivity(
            label=classification.sensitivity_label,
            classification=classification,
            override=None,
        )
    return EffectiveSensitivity(
        label=override.new_label,
        classification=classification,
        override=override,
    )


def append_override(
    session: Session,
    *,
    document_id: UUID,
    overridden_by: UUID,
    original_label: SensitivityLabel,
    new_label: SensitivityLabel,
    justification: str,
) -> ManualOverride:
    """Record one human relabel and return the row, without committing.

    ``overridden_at`` is ``clock_timestamp()``, not transaction-scoped
    ``now()``. Two serialized writers can start in either order; the one that
    inserts later must sort later or the resolver would treat the predecessor
    as current.
    """
    stamped_at = session.scalar(select(func.clock_timestamp()))
    row = ManualOverride(
        document_id=document_id,
        overridden_by=overridden_by,
        original_label=original_label,
        new_label=new_label,
        justification=justification,
        overridden_at=stamped_at,
    )
    session.add(row)
    session.flush()
    return row


def override_audit_payload(*, row: ManualOverride) -> dict[str, Any]:
    """Audit payload for one override. JSON primitives only."""
    return {
        "override_id": str(row.id),
        "document_id": str(row.document_id),
        "overridden_by": str(row.overridden_by),
        "original_label": row.original_label.value,
        "new_label": row.new_label.value,
        "justification": row.justification,
    }
