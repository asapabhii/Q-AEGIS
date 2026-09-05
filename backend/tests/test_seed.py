"""The development-only user seed, :mod:`app.db.seed`.

Tested because the API's identity stub depends on it: with no seeded user for a
role, every write that references ``users.id`` fails. The seed is a stub and is
labelled one, but it is a stub other code relies on, so its two real properties,
one account per role and idempotency, are asserted rather than assumed.
"""

import pytest
from sqlalchemy import Engine, text
from sqlalchemy.orm import Session

from app.db import seed
from app.db.enums import UserRole
from app.db.models import User
from app.db.repositories import identity
from app.db.seed import (
    DEV_EMAIL_DOMAIN,
    dev_display_name,
    dev_email,
    seed_development_users,
)


def test_every_role_gets_an_account(db_session: Session) -> None:
    """A role with no user is a role that cannot act, so none may be missing."""
    seed_development_users(db_session)

    for role in UserRole:
        user = identity.first_by_role(db_session, role)
        assert user is not None
        assert user.role is role


def test_seeding_twice_changes_nothing(db_session: Session) -> None:
    """Idempotent, so running it again after a migration is harmless.

    Without this, a second run would fail on the unique email constraint and
    someone would reasonably conclude the database was broken.
    """
    seed_development_users(db_session)
    before = db_session.query(User).count()

    seed_development_users(db_session)

    assert db_session.query(User).count() == before


def test_seeded_accounts_are_identifiable_as_seeded(db_session: Session) -> None:
    """Nobody should mistake one of these for a real account.

    ``.local`` is reserved and cannot resolve publicly, so a seeded address can
    never collide with a real mailbox, and the display name says so in words.
    """
    seed_development_users(db_session)

    for role in UserRole:
        user = identity.find_by_email(db_session, dev_email(role))
        assert user is not None
        assert user.email.endswith(f"@{DEV_EMAIL_DOMAIN}")
        assert "seeded" in dev_display_name(role).lower()
        assert "seeded" in user.name.lower()


def test_the_seed_returns_what_it_ensured(db_session: Session) -> None:
    """The return value is the mapping callers use, so it must be complete."""
    seeded = seed_development_users(db_session)
    assert set(seeded) == set(UserRole)
    assert seeded[UserRole.AUDITOR] == dev_email(UserRole.AUDITOR)


def test_the_entry_point_commits_and_reports(
    migrated_scratch_engine: Engine, capsys: pytest.CaptureFixture[str]
) -> None:
    """``python -m app.db.seed`` has to actually persist, and say what it did.

    Run against a scratch database because this is the one path that commits;
    every other test here rolls back. The printed output is what tells someone
    which addresses to send requests as, so an entry point that seeded silently
    would leave them guessing.
    """
    seed.main()

    printed = capsys.readouterr().out
    for role in UserRole:
        assert dev_email(role) in printed

    with migrated_scratch_engine.connect() as connection:
        count = connection.execute(
            text(f"SELECT count(*) FROM users WHERE email LIKE '%@{DEV_EMAIL_DOMAIN}'")
        ).scalar_one()
    assert count == len(UserRole)


def test_an_existing_user_is_not_duplicated_by_role(db_session: Session) -> None:
    """A real user already holding a role does not block or duplicate seeding."""
    identity.create_user(
        db_session,
        name="Real Person",
        email="real.person@example.test",
        role=UserRole.AUDITOR,
    )

    seed_development_users(db_session)

    auditors = db_session.query(User).filter(User.role == UserRole.AUDITOR).all()
    assert len(auditors) == 2
