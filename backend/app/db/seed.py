"""Development-only seed data.

THIS IS A DEVELOPMENT STUB, not fixture data for any deployed environment, and
not a substitute for user management. It exists for one reason: ``documents``,
``manual_overrides``, ``policy_rules``, and ``audit_log`` all reference
``users.id``, while the API's identity source is still a header-trusting stub
(:mod:`app.api.deps`) that knows a caller's role and nothing else. Without a real
row per role, no request could satisfy those foreign keys.

Deliberately NOT an Alembic migration. Migrations describe schema, and a data
migration that inserts people into a table would run against every database the
migration chain is ever applied to, including any future non-development one.
This is a script, invoked on purpose:

    cd backend
    python -m app.db.seed

Idempotent, so running it twice is harmless. When real authentication lands,
delete this module and the ``first_by_role`` lookup that depends on it, rather
than leaving seeded accounts in place as a convenience.
"""

from sqlalchemy.orm import Session

from app.db.enums import UserRole
from app.db.repositories import identity
from app.db.session import session_scope

#: Domain for seeded accounts. ``.local`` is reserved for local use and cannot
#: resolve publicly, so a seeded address can never collide with a real mailbox or
#: be mistaken for one.
DEV_EMAIL_DOMAIN = "dev.qaegis.local"


def dev_email(role: UserRole) -> str:
    """Return the seeded account address for ``role``."""
    return f"{role.value}@{DEV_EMAIL_DOMAIN}"


def dev_display_name(role: UserRole) -> str:
    """Return a human-readable name that says plainly what the account is."""
    return f"Dev {role.value.replace('_', ' ').title()} (seeded)"


def seed_development_users(session: Session) -> dict[UserRole, str]:
    """Ensure one seeded user exists per role, without committing.

    Args:
        session: Active session.

    Returns:
        A mapping of role to the seeded account's email, for every role in
        :class:`~app.db.enums.UserRole`.
    """
    seeded: dict[UserRole, str] = {}
    for role in UserRole:
        email = dev_email(role)
        if identity.find_by_email(session, email) is None:
            identity.create_user(
                session, name=dev_display_name(role), email=email, role=role
            )
        seeded[role] = email
    return seeded


def main() -> None:
    """Seed the configured database and report what was ensured."""
    with session_scope() as session:
        seeded = seed_development_users(session)
    for role, email in seeded.items():
        print(f"{role.value:20} {email}")


if __name__ == "__main__":  # pragma: no cover - exercised via main() in tests
    main()
