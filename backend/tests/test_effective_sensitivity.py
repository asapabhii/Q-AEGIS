"""Effective sensitivity resolution, ``PRD.md`` FR-12.

The policy gate and the override write path share one function. These tests
pin that function without HTTP so a later change cannot start comparing
timestamps or falling back to the latest classification after an override.
"""

import threading
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.classifier.labels import SensitivityLabel, SensitivitySource
from app.db.enums import UserRole
from app.db.models import ClassificationMetadata, Document, ManualOverride, User
from app.db.repositories import documents as documents_repo
from app.db.repositories import overrides as override_repo
from app.db.seed import dev_email, seed_development_users
from tests import factories

JUSTIFICATION = "Reviewed with the data owner and reclassified."


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


def test_appended_overrides_order_by_clock_time_not_transaction_now(
    db_session: Session,
    registered_document: Document,
    seeded_users: dict,
) -> None:
    """Two inserts in one transaction must not share ``now()`` and flip latest."""
    factories.make_classification(
        db_session, registered_document, label=SensitivityLabel.PUBLIC
    )
    actor = seeded_users[UserRole.SECURITY_ANALYST].id
    first = override_repo.append_override(
        db_session,
        document_id=registered_document.id,
        overridden_by=actor,
        original_label=SensitivityLabel.PUBLIC,
        new_label=SensitivityLabel.INTERNAL,
        justification=JUSTIFICATION,
    )
    second = override_repo.append_override(
        db_session,
        document_id=registered_document.id,
        overridden_by=actor,
        original_label=SensitivityLabel.INTERNAL,
        new_label=SensitivityLabel.RESTRICTED,
        justification=JUSTIFICATION,
    )

    assert second.overridden_at >= first.overridden_at
    latest = override_repo.latest_for_document(db_session, registered_document.id)
    assert latest is not None
    assert latest.id == second.id
    assert latest.new_label is SensitivityLabel.RESTRICTED


def _commit_classified_document(engine: Engine) -> tuple[UUID, UUID]:
    """Seed one classified document on a scratch database and commit it."""
    with Session(engine) as session:
        seed_development_users(session)
        owner = (
            session.query(User)
            .filter(User.email == dev_email(UserRole.DATA_OWNER))
            .one()
        )
        analyst = (
            session.query(User)
            .filter(User.email == dev_email(UserRole.SECURITY_ANALYST))
            .one()
        )
        document = documents_repo.register_document(
            session, uploaded_by=owner.id, filename="race.pdf"
        )
        factories.make_classification(session, document, label=SensitivityLabel.PUBLIC)
        session.commit()
        return document.id, analyst.id


def _write_override(
    engine: Engine,
    document_id: UUID,
    actor_id: UUID,
    new_label: SensitivityLabel,
    barrier: threading.Barrier,
) -> str:
    """Lock, resolve, and append, matching the API write path."""
    with Session(engine) as session:
        barrier.wait()
        override_repo.lock_document(session, document_id)
        effective = override_repo.effective_for_document(session, document_id)
        if effective is None or effective.label is new_label:
            session.rollback()
            return "rejected"
        override_repo.append_override(
            session,
            document_id=document_id,
            overridden_by=actor_id,
            original_label=effective.label,
            new_label=new_label,
            justification=JUSTIFICATION,
        )
        session.commit()
        return effective.label.value


def test_concurrent_same_label_overrides_leave_one_row(
    migrated_scratch_engine: Engine,
) -> None:
    """The second writer must re-read after the lock, not reuse the AI label."""
    document_id, actor_id = _commit_classified_document(migrated_scratch_engine)
    barrier = threading.Barrier(2)
    outcomes: list[str] = []

    def run() -> None:
        outcomes.append(
            _write_override(
                migrated_scratch_engine,
                document_id,
                actor_id,
                SensitivityLabel.INTERNAL,
                barrier,
            )
        )

    first = threading.Thread(target=run)
    second = threading.Thread(target=run)
    first.start()
    second.start()
    first.join()
    second.join()

    assert sorted(outcomes) == ["PUBLIC", "rejected"]
    with Session(migrated_scratch_engine) as session:
        rows = (
            session.query(ManualOverride)
            .filter(ManualOverride.document_id == document_id)
            .all()
        )
        assert len(rows) == 1
        assert rows[0].original_label is SensitivityLabel.PUBLIC
        assert rows[0].new_label is SensitivityLabel.INTERNAL


def test_concurrent_overrides_snapshot_the_previous_effective_label(
    migrated_scratch_engine: Engine,
) -> None:
    """The later row's original_label is the earlier row's new_label."""
    document_id, actor_id = _commit_classified_document(migrated_scratch_engine)
    barrier = threading.Barrier(2)
    targets = (SensitivityLabel.INTERNAL, SensitivityLabel.CONFIDENTIAL)
    outcomes: list[str] = []

    def run(new_label: SensitivityLabel) -> None:
        outcomes.append(
            _write_override(
                migrated_scratch_engine,
                document_id,
                actor_id,
                new_label,
                barrier,
            )
        )

    threads = [threading.Thread(target=run, args=(target,)) for target in targets]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert "PUBLIC" in outcomes
    assert "rejected" not in outcomes
    assert len(outcomes) == 2
    with Session(migrated_scratch_engine) as session:
        rows = (
            session.query(ManualOverride)
            .filter(ManualOverride.document_id == document_id)
            .order_by(ManualOverride.overridden_at.asc(), ManualOverride.id.asc())
            .all()
        )
        assert len(rows) == 2
        assert rows[0].original_label is SensitivityLabel.PUBLIC
        assert rows[1].original_label is rows[0].new_label
