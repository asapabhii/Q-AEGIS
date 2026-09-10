"""Effective sensitivity resolution, ``PRD.md`` FR-12.

The policy gate and the override write path share one function. These tests
pin that function without HTTP so a later change cannot start comparing
timestamps or falling back to the latest classification after an override.
"""

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy.orm import Session

from app.classifier.labels import SensitivityLabel, SensitivitySource
from app.db.enums import UserRole
from app.db.models import ClassificationMetadata, Document
from app.db.repositories import overrides as override_repo
from tests import factories


def test_effective_label_is_the_latest_classification_when_unoverridden(
    db_session: Session, registered_document: Document
) -> None:
    factories.make_classification(
        db_session, registered_document, label=SensitivityLabel.INTERNAL
    )

    effective = override_repo.effective_for_document(db_session, registered_document.id)

    assert effective is not None
    assert effective.label is SensitivityLabel.INTERNAL
    assert effective.source is SensitivitySource.CLASSIFICATION
    assert effective.override_id is None


def test_effective_label_is_the_latest_override(
    db_session: Session,
    registered_document: Document,
    seeded_users: dict,
) -> None:
    factories.make_classification(
        db_session, registered_document, label=SensitivityLabel.PUBLIC
    )
    factories.make_override(
        db_session,
        registered_document,
        seeded_users[UserRole.SECURITY_ANALYST].id,
        original=SensitivityLabel.PUBLIC,
        new=SensitivityLabel.RESTRICTED,
    )

    effective = override_repo.effective_for_document(db_session, registered_document.id)

    assert effective is not None
    assert effective.label is SensitivityLabel.RESTRICTED
    assert effective.source is SensitivitySource.MANUAL_OVERRIDE
    assert effective.override_id is not None


def test_a_later_classification_does_not_retract_an_override(
    db_session: Session,
    registered_document: Document,
    seeded_users: dict,
) -> None:
    factories.make_classification(
        db_session, registered_document, label=SensitivityLabel.PUBLIC
    )
    factories.make_override(
        db_session,
        registered_document,
        seeded_users[UserRole.SECURITY_ANALYST].id,
        original=SensitivityLabel.PUBLIC,
        new=SensitivityLabel.CONFIDENTIAL,
    )
    db_session.add(
        ClassificationMetadata(
            document_id=registered_document.id,
            sensitivity_label=SensitivityLabel.RESTRICTED,
            confidence_score=Decimal("0.9000"),
            model_version="test-later-0.1.0",
            is_defaulted=False,
            classified_at=datetime.now(timezone.utc) + timedelta(hours=1),
        )
    )
    db_session.flush()

    effective = override_repo.effective_for_document(db_session, registered_document.id)

    assert effective is not None
    assert effective.label is SensitivityLabel.CONFIDENTIAL
    assert effective.classification.sensitivity_label is SensitivityLabel.RESTRICTED


def test_effective_label_is_none_without_a_classification(
    db_session: Session,
    registered_document: Document,
    seeded_users: dict,
) -> None:
    """An override-only row is not an AI classification to override."""
    factories.make_override(
        db_session,
        registered_document,
        seeded_users[UserRole.SECURITY_ANALYST].id,
    )

    assert (
        override_repo.effective_for_document(db_session, registered_document.id) is None
    )
