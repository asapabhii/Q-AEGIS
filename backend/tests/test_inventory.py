"""Unit tests for the FR-14 snapshot assembler.

Property cases need no database. The unknown-id path uses a real session.
"""

from uuid import uuid4

from sqlalchemy.orm import Session

from app.classifier.labels import SensitivityLabel, SensitivitySource
from app.db.enums import DocumentStatus
from app.db.models import ClassificationMetadata, Document, ManualOverride
from app.db.repositories.inventory import DocumentSnapshot, get_snapshot


def _document() -> Document:
    return Document(
        id=uuid4(),
        uploaded_by=uuid4(),
        filename="report.pdf",
        current_status=DocumentStatus.REGISTERED,
    )


def test_a_document_with_no_classification_has_no_label() -> None:
    snapshot = DocumentSnapshot(
        document=_document(),
        classification=None,
        override=None,
        risk=None,
        trust=None,
        decision=None,
        profile=None,
    )
    assert snapshot.sensitivity_label is None
    assert snapshot.label_source is None


def test_a_classification_without_an_override_is_the_effective_label() -> None:
    classification = ClassificationMetadata(
        document_id=uuid4(),
        sensitivity_label=SensitivityLabel.RESTRICTED,
        confidence_score="0.9000",
        model_version="stub",
        is_defaulted=False,
    )
    snapshot = DocumentSnapshot(
        document=_document(),
        classification=classification,
        override=None,
        risk=None,
        trust=None,
        decision=None,
        profile=None,
    )
    assert snapshot.sensitivity_label is SensitivityLabel.RESTRICTED
    assert snapshot.label_source is SensitivitySource.CLASSIFICATION


def test_an_override_wins_over_the_classification() -> None:
    document_id = uuid4()
    classification = ClassificationMetadata(
        document_id=document_id,
        sensitivity_label=SensitivityLabel.RESTRICTED,
        confidence_score="0.9000",
        model_version="stub",
        is_defaulted=False,
    )
    override = ManualOverride(
        document_id=document_id,
        overridden_by=uuid4(),
        original_label=SensitivityLabel.RESTRICTED,
        new_label=SensitivityLabel.INTERNAL,
        justification="Reviewed with the data owner and reclassified.",
    )
    snapshot = DocumentSnapshot(
        document=_document(),
        classification=classification,
        override=override,
        risk=None,
        trust=None,
        decision=None,
        profile=None,
    )
    assert snapshot.sensitivity_label is SensitivityLabel.INTERNAL
    assert snapshot.label_source is SensitivitySource.MANUAL_OVERRIDE


def test_an_override_without_a_classification_does_not_invent_a_label() -> None:
    override = ManualOverride(
        document_id=uuid4(),
        overridden_by=uuid4(),
        original_label=SensitivityLabel.RESTRICTED,
        new_label=SensitivityLabel.INTERNAL,
        justification="Reviewed with the data owner and reclassified.",
    )
    snapshot = DocumentSnapshot(
        document=_document(),
        classification=None,
        override=override,
        risk=None,
        trust=None,
        decision=None,
        profile=None,
    )
    assert snapshot.sensitivity_label is None
    assert snapshot.label_source is None


def test_get_snapshot_returns_none_for_an_unknown_document(db_session: Session) -> None:
    assert get_snapshot(db_session, uuid4()) is None
