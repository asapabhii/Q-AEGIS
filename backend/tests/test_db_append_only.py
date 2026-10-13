"""Database-level append-only enforcement, ``SPEC.md`` 3.8, ``PRD.md`` FR-7.

These tests exercise the plpgsql triggers installed by the initial migration, not
the repository layer. That distinction is the point: ``SPEC.md`` 3.8 requires the
guarantee at the database level precisely so it holds against a direct SQL
statement, a future service written in another language, or a well-meaning
migration, none of which go through the repositories.

Every attempt below is made with raw SQL rather than the ORM, so nothing in the
Python layer can be credited for a refusal the database is supposed to make.
"""

from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime, timezone

import psycopg
import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db.enums import AuditEventType, UserRole
from app.db.models import (
    DELETE_REJECTED_TABLES,
    UPDATE_REJECTED_TABLES,
    AuditLog,
    Document,
    User,
)
from app.db.repositories import audit as audit_repo
from app.db.repositories import checkpoint as checkpoint_repo
from tests import factories

#: Every append-only table paired with a column an UPDATE would plausibly target.
#: The column matters: an UPDATE naming a nonexistent column fails on the column
#: rather than on the trigger, and the test would pass without proving anything.
UPDATE_TARGETS = {
    "classification_metadata": "model_version = 'tampered-0.0.0'",
    "risk_scores": "risk_value = 0.999",
    "trust_scores": "consensus_value = 0.999",
    "crypto_profiles": "profile_type = 'aes256'",
    "audit_log": "event_type = 'tampered'",
    "audit_signing_keys": "algorithm = 'tampered'",
    "audit_checkpoints": "tree_size = 999999",
}


@contextmanager
def statement_expected_to_fail(session: Session) -> Iterator[None]:
    """Run a statement whose failure aborts the transaction, then recover.

    A rejected statement leaves Postgres refusing everything until the
    transaction unwinds, so the savepoint has to be rolled back explicitly.
    Wrapping the body in ``session.begin_nested()`` as a context manager does not
    work: ``pytest.raises`` catches the error first, so the block exits normally
    and tries to RELEASE a savepoint inside an already-aborted transaction.
    """
    savepoint = session.begin_nested()
    try:
        yield
    finally:
        savepoint.rollback()


def assert_rejected_by_append_only_trigger(exc_info: pytest.ExceptionInfo) -> None:
    """Assert the failure is the append-only trigger, not some other error.

    The migration raises with ``ERRCODE = 'restrict_violation'`` (SQLSTATE 23001)
    specifically so this can be asserted on the exception type. Matching message
    text alone would keep passing if the trigger were replaced by an unrelated
    constraint that happened to use the same words.
    """
    assert isinstance(exc_info.value.orig, psycopg.errors.RestrictViolation)
    assert "append-only" in str(exc_info.value.orig)


@pytest.fixture
def one_row_per_history_table(
    db_session: Session,
    registered_document: Document,
    seeded_users: dict[UserRole, User],
) -> dict[str, str]:
    """Populate one row in every append-only table and return their ids by table."""
    risk_score = factories.make_risk_score(db_session, registered_document)
    trust_score = factories.make_trust_score(
        db_session, registered_document, risk_score
    )
    classification = factories.make_classification(db_session, registered_document)
    crypto_profile = factories.make_crypto_profile(
        db_session, registered_document, trust_score
    )
    entry = audit_repo.append_entry(
        db_session,
        event_type=AuditEventType.CLASSIFICATION_COMPLETED.value,
        document_id=registered_document.id,
        actor_id=seeded_users[UserRole.DATA_OWNER].id,
        payload={"note": "seed entry for trigger tests"},
    )
    # Seeded directly through the repository, not the checkpoint service: these
    # rows only exercise the append-only triggers, so a real ML-DSA-87 signature
    # (which would need liboqs on the host) is unnecessary. The values are
    # syntactically valid placeholders, never verified here.
    signing_key = checkpoint_repo.insert_signing_key(
        db_session,
        algorithm="ML-DSA-87",
        public_key="ab" * 32,
        wrapped_secret_key=b"seed-wrapped-secret-key",
    )
    checkpoint = checkpoint_repo.insert_checkpoint(
        db_session,
        document_id=registered_document.id,
        signing_key_id=signing_key.id,
        tree_size=1,
        merkle_root="a" * 64,
        signature="cd" * 32,
        signed_at=datetime.now(timezone.utc),
    )
    return {
        "classification_metadata": str(classification.id),
        "risk_scores": str(risk_score.id),
        "trust_scores": str(trust_score.id),
        "crypto_profiles": str(crypto_profile.id),
        "audit_log": str(entry.id),
        "audit_signing_keys": str(signing_key.id),
        "audit_checkpoints": str(checkpoint.id),
    }


@pytest.mark.parametrize("table", UPDATE_REJECTED_TABLES)
def test_update_is_rejected_on_every_append_only_table(
    db_session: Session, one_row_per_history_table: dict[str, str], table: str
) -> None:
    """A new decision is a new row; a past one cannot be rewritten."""
    statement = text(f"UPDATE {table} SET {UPDATE_TARGETS[table]} WHERE id = :row_id")

    with statement_expected_to_fail(db_session):
        with pytest.raises(IntegrityError) as exc_info:
            db_session.execute(statement, {"row_id": one_row_per_history_table[table]})

    assert_rejected_by_append_only_trigger(exc_info)


@pytest.mark.parametrize("table", UPDATE_REJECTED_TABLES)
def test_the_row_is_unchanged_after_a_rejected_update(
    db_session: Session, one_row_per_history_table: dict[str, str], table: str
) -> None:
    """The refusal leaves the data as it was, rather than partially applying."""
    row_id = one_row_per_history_table[table]
    column = UPDATE_TARGETS[table].split("=")[0].strip()
    select_column = text(f"SELECT {column} FROM {table} WHERE id = :row_id")

    before = db_session.execute(select_column, {"row_id": row_id}).scalar_one()

    with statement_expected_to_fail(db_session):
        with pytest.raises(IntegrityError):
            db_session.execute(
                text(f"UPDATE {table} SET {UPDATE_TARGETS[table]} WHERE id = :row_id"),
                {"row_id": row_id},
            )

    after = db_session.execute(select_column, {"row_id": row_id}).scalar_one()
    assert after == before


@pytest.mark.parametrize("table", DELETE_REJECTED_TABLES)
def test_delete_is_rejected_on_the_audit_log(
    db_session: Session, one_row_per_history_table: dict[str, str], table: str
) -> None:
    """``PRD.md`` FR-7: no code path can delete an existing entry.

    Covers ``audit_log`` and, held to the same bar, the checkpoint tables: a
    Signed Tree Head and the key that signed it are tamper-evidence, defeated
    the moment either can be deleted.
    """
    with statement_expected_to_fail(db_session):
        with pytest.raises(IntegrityError) as exc_info:
            db_session.execute(
                text(f"DELETE FROM {table} WHERE id = :row_id"),
                {"row_id": one_row_per_history_table[table]},
            )

    assert_rejected_by_append_only_trigger(exc_info)


@pytest.mark.parametrize("table", DELETE_REJECTED_TABLES)
def test_unqualified_delete_is_rejected_on_the_audit_log(
    db_session: Session, one_row_per_history_table: dict[str, str], table: str
) -> None:
    """A DELETE with no WHERE clause is refused too, not just a targeted one."""
    with statement_expected_to_fail(db_session):
        with pytest.raises(IntegrityError) as exc_info:
            db_session.execute(text(f"DELETE FROM {table}"))

    assert_rejected_by_append_only_trigger(exc_info)


@pytest.mark.parametrize("table", DELETE_REJECTED_TABLES)
def test_truncate_is_rejected_on_the_audit_log(
    db_session: Session, one_row_per_history_table: dict[str, str], table: str
) -> None:
    """TRUNCATE does not fire row-level triggers, so it needs its own guard.

    Without the statement-level trigger the whole log would stay erasable in one
    statement while every DELETE test above still passed, which is the most
    dangerous shape this bug could take: the protection appears to work.

    CASCADE, not a bare TRUNCATE: ``audit_checkpoints`` has a foreign key to
    ``audit_signing_keys``, so Postgres refuses a bare ``TRUNCATE
    audit_signing_keys`` with ``FeatureNotSupported`` before any trigger runs.
    CASCADE is the form that would actually erase the table, so it is the form
    the guard must stop; it also fires the BEFORE TRUNCATE trigger on every
    table in the cascade, which is what reaches our guard here.
    """
    with statement_expected_to_fail(db_session):
        with pytest.raises(IntegrityError) as exc_info:
            db_session.execute(text(f"TRUNCATE {table} CASCADE"))

    assert_rejected_by_append_only_trigger(exc_info)


def test_insert_is_still_permitted_on_an_append_only_table(
    db_session: Session,
    registered_document: Document,
    seeded_users: dict[UserRole, User],
) -> None:
    """Append-only means append is allowed. The guard must not block writes."""
    entry = audit_repo.append_entry(
        db_session,
        event_type=AuditEventType.CLASSIFICATION_COMPLETED.value,
        document_id=registered_document.id,
        actor_id=seeded_users[UserRole.DATA_OWNER].id,
        payload={"appended": True},
    )
    assert entry.id is not None
    assert db_session.get(AuditLog, entry.id) is not None


def test_delete_remains_permitted_on_the_history_tables(
    db_session: Session, one_row_per_history_table: dict[str, str]
) -> None:
    """Documents the deliberate asymmetry, so a future change is a decision.

    The four history tables block UPDATE only, which is what "never updated in
    place" requires. ``audit_log`` is the one table whose guarantee ``PRD.md``
    FR-7 states absolutely. If DELETE is ever blocked on the history tables too,
    this test fails and whoever changed it has to say why here.
    """
    db_session.execute(
        text("DELETE FROM crypto_profiles WHERE id = :row_id"),
        {"row_id": one_row_per_history_table["crypto_profiles"]},
    )


def test_documents_status_is_updatable(
    db_session: Session, registered_document: Document
) -> None:
    """``documents`` is not append-only; its status pointer is meant to move."""
    db_session.execute(
        text("UPDATE documents SET current_status = 'archived' WHERE id = :row_id"),
        {"row_id": str(registered_document.id)},
    )
    db_session.expire(registered_document)
    assert registered_document.current_status.value == "archived"
