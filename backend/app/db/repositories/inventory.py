"""Current per-document snapshot for the FR-14 inventory.

History tables are append-only. This module reads the latest row of each
and does not write. A later classification, score, or selection is a new
row; the snapshot follows that row. An override still wins over a later
classification, same rule as the policy gate.
"""

from dataclasses import dataclass
from typing import Any, TypeVar
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.classifier.labels import SensitivityLabel, SensitivitySource
from app.db.models import (
    ClassificationMetadata,
    CryptoProfile,
    Document,
    ManualOverride,
    PolicyDecision,
    RiskScore,
    TrustScore,
)
from app.db.repositories import classification as classification_repo
from app.db.repositories import crypto as crypto_repo
from app.db.repositories import documents as documents_repo
from app.db.repositories import overrides as override_repo
from app.db.repositories import policy as policy_repo
from app.db.repositories import risk as risk_repo
from app.db.repositories import trust as trust_repo

T = TypeVar("T")


@dataclass(frozen=True)
class DocumentSnapshot:
    """Latest identity, effective label, scores, gate, and protection."""

    document: Document
    classification: ClassificationMetadata | None
    override: ManualOverride | None
    risk: RiskScore | None
    trust: TrustScore | None
    decision: PolicyDecision | None
    profile: CryptoProfile | None

    @property
    def sensitivity_label(self) -> SensitivityLabel | None:
        """Effective label, or ``None`` when nothing has been classified."""
        if self.classification is None:
            return None
        if self.override is not None:
            return self.override.new_label
        return self.classification.sensitivity_label

    @property
    def label_source(self) -> SensitivitySource | None:
        """Where the effective label was read from, if a label exists."""
        if self.classification is None:
            return None
        if self.override is not None:
            return SensitivitySource.MANUAL_OVERRIDE
        return SensitivitySource.CLASSIFICATION


def get_snapshot(session: Session, document_id: UUID) -> DocumentSnapshot | None:
    """One document's current snapshot, or ``None`` if the document is unknown."""
    document = documents_repo.get_document(session, document_id)
    if document is None:
        return None
    return DocumentSnapshot(
        document=document,
        classification=classification_repo.latest_for_document(session, document_id),
        override=override_repo.latest_for_document(session, document_id),
        risk=risk_repo.latest_for_document(session, document_id),
        trust=trust_repo.latest_for_document(session, document_id),
        decision=policy_repo.latest_for_document(session, document_id),
        profile=crypto_repo.latest_for_document(session, document_id),
    )


def list_snapshots(session: Session) -> list[DocumentSnapshot]:
    """Current snapshot for every document, newest registration first.

    Latest rows are loaded in six queries, not one per document.
    """
    documents = documents_repo.list_documents(session)
    if not documents:
        return []
    classifications = _latest_by_document(
        session,
        ClassificationMetadata,
        ClassificationMetadata.classified_at.desc(),
        ClassificationMetadata.id.desc(),
    )
    overrides = _latest_by_document(
        session,
        ManualOverride,
        ManualOverride.overridden_at.desc(),
        ManualOverride.id.desc(),
    )
    risks = _latest_by_document(
        session,
        RiskScore,
        RiskScore.computed_at.desc(),
        RiskScore.id.desc(),
    )
    trusts = _latest_by_document(
        session,
        TrustScore,
        TrustScore.computed_at.desc(),
        TrustScore.id.desc(),
    )
    decisions = _latest_by_document(
        session,
        PolicyDecision,
        PolicyDecision.decided_at.desc(),
        PolicyDecision.id.desc(),
    )
    profiles = _latest_by_document(
        session,
        CryptoProfile,
        CryptoProfile.selected_at.desc(),
        CryptoProfile.id.desc(),
    )
    return [
        DocumentSnapshot(
            document=document,
            classification=classifications.get(document.id),
            override=overrides.get(document.id),
            risk=risks.get(document.id),
            trust=trusts.get(document.id),
            decision=decisions.get(document.id),
            profile=profiles.get(document.id),
        )
        for document in documents
    ]


def _latest_by_document(
    session: Session,
    model: type[T],
    *order_cols: Any,
) -> dict[UUID, T]:
    """PostgreSQL ``DISTINCT ON (document_id)`` for one history table."""
    document_id = model.document_id  # type: ignore[attr-defined]
    return {
        row.document_id: row
        for row in session.scalars(
            select(model).distinct(document_id).order_by(document_id, *order_cols)
        ).all()
    }
