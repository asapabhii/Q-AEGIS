"""Development-only seed data with local login passwords.

Seeded accounts use a known local-only password (see ``DEV_PASSWORD``) so
JWT login works after ``python -m app.db.seed``. Not for any shared or
deployed environment.
"""

from sqlalchemy.orm import Session

from app.auth.security import hash_password
from app.db.enums import UserRole
from app.db.repositories import identity
from app.db.session import session_scope

DEV_EMAIL_DOMAIN = "dev.qaegis.local"

#: Known password for every seeded account. Local/dev only.
DEV_PASSWORD = "local-dev-only-password"


def dev_email(role: UserRole) -> str:
    """Return the seeded account address for ``role``."""
    return f"{role.value}@{DEV_EMAIL_DOMAIN}"


def dev_display_name(role: UserRole) -> str:
    """Return a human-readable name that says plainly what the account is."""
    return f"Dev {role.value.replace('_', ' ').title()} (seeded)"


def seed_development_users(session: Session) -> dict[UserRole, str]:
    """Ensure one seeded user exists per role, with a password hash."""
    password_hash = hash_password(DEV_PASSWORD)
    seeded: dict[UserRole, str] = {}
    for role in UserRole:
        email = dev_email(role)
        existing = identity.find_by_email(session, email)
        if existing is None:
            identity.create_user(
                session,
                name=dev_display_name(role),
                email=email,
                role=role,
                password_hash=password_hash,
            )
        elif not existing.password_hash:
            existing.password_hash = password_hash
        seeded[role] = email
    return seeded


def main() -> None:
    """Seed the configured database and report what was ensured."""
    with session_scope() as session:
        seeded = seed_development_users(session)
    print(f"password (all seeded accounts): {DEV_PASSWORD}")
    for role, email in seeded.items():
        print(f"{role.value:20} {email}")


if __name__ == "__main__":  # pragma: no cover
    main()
