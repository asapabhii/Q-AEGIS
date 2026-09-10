"""Read and append ``manual_overrides``, ``PRD.md`` FR-12.

Append only. There is no update or clear function. A later classification
does not retract a human override; only another override changes the
effective label. That rule is the product contract, not an implementation
shortcut: the gate must not let the stub classifier silently undo an analyst.
"""

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.classifier.labels import SensitivityLabel, SensitivitySource
from app.db.models import ClassificationMetadata, ManualOverride
from app.db.repositories import classification as classification_repo


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


def latest_for_document(session: Session, document_id: UUID) -> ManualOverride | None:
    """Return the most recent override for a document, if any.

    Ordered by ``overridden_at`` then ``id``. The tiebreak matters because
    ``overridden_at`` defaults to the transaction timestamp, so two overrides
    written in one transaction would otherwise have no defined "most recent".
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
    """Record one human relabel and return the row, without committing."""
    row = ManualOverride(
        document_id=document_id,
        overridden_by=overridden_by,
        original_label=original_label,
        new_label=new_label,
        justification=justification,
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
