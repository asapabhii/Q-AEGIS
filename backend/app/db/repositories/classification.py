"""Append to ``classification_metadata``, ``SPEC.md`` 3.2, ``PRD.md`` FR-1.

Append only. There is no update function, and adding one would produce a helper
whose only possible outcome is the database trigger raising: a document is
reclassified by writing a new row that supersedes the previous one.
"""

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.classifier.stub_classifier import ClassificationResult
from app.db.models import ClassificationMetadata

#: Decimal places stored for ``confidence_score``, matching ``numeric(5,4)``.
CONFIDENCE_DECIMAL_PLACES = 4


def append_classification(
    session: Session,
    *,
    document_id: UUID,
    result: ClassificationResult,
) -> ClassificationMetadata:
    """Record one classification run and return the row, without committing.

    ``confidence`` is converted through ``str`` rather than passed as a float.
    ``Decimal(0.6667)`` from a float carries the float's full binary expansion and
    would be rounded by the database on the way in; ``Decimal("0.6667")`` is the
    number the classifier actually reported.
    """
    row = ClassificationMetadata(
        document_id=document_id,
        sensitivity_label=result.sensitivity_label,
        confidence_score=Decimal(str(result.confidence)),
        model_version=result.model_version,
        is_defaulted=result.is_defaulted,
    )
    session.add(row)
    session.flush()
    return row


def latest_for_document(
    session: Session, document_id: UUID
) -> ClassificationMetadata | None:
    """Return the most recent classification for a document, if any.

    Ordered by ``classified_at`` then ``id``. The tiebreak matters because
    ``classified_at`` defaults to the transaction timestamp, so two classifications
    written in one transaction would otherwise have no defined "most recent".
    """
    return session.scalars(
        select(ClassificationMetadata)
        .where(ClassificationMetadata.document_id == document_id)
        .order_by(
            ClassificationMetadata.classified_at.desc(),
            ClassificationMetadata.id.desc(),
        )
        .limit(1)
    ).one_or_none()


def classification_audit_payload(
    *,
    document_id: UUID,
    result: ClassificationResult,
    classification_id: UUID,
) -> dict[str, Any]:
    """Build the audit payload for one classification.

    Carries the full decision, including the four fields deliberately absent from
    ``classification_metadata``: ``base_label``, ``confidence_threshold``,
    ``matched_keywords``, and ``rationale``. The typed table holds the schema's
    contract; the audit payload holds the complete record, so explainability
    survives without the table accumulating columns tied to the current keyword
    stub (see ``docs/data-dictionary.md``).

    Every value is a JSON primitive. UUIDs and the confidence float are converted
    here rather than left for the serialiser, because
    :func:`app.db.repositories.audit.normalize_payload` refuses to coerce types
    silently.
    """
    return {
        "classification_id": str(classification_id),
        "document_id": str(document_id),
        "sensitivity_label": result.sensitivity_label.value,
        "confidence": result.confidence,
        "model_version": result.model_version,
        "is_defaulted": result.is_defaulted,
        "base_label": result.base_label.value,
        "confidence_threshold": result.confidence_threshold,
        "matched_keywords": list(result.matched_keywords),
        "rationale": result.rationale,
    }
