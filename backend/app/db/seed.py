"""Development-only seed data with local login passwords.

Seeded accounts get a password from ``QAEGIS_DEV_SEED_PASSWORD`` (see
``.env.example``). Never use this seed against a shared or deployed database.
"""

from __future__ import annotations

import os

from sqlalchemy.orm import Session

from app.auth.security import hash_password
from app.db.enums import UserRole
from app.db.repositories import identity
from app.db.session import session_scope

DEV_EMAIL_DOMAIN = "dev.qaegis.local"


def resolve_dev_password() -> str:
    """Return the local seed password from the environment.

    Requires ``QAEGIS_DEV_SEED_PASSWORD`` so a reusable credential is not
    hard-coded in the repository. Local setup: copy from ``.env.example``.
    Loads the repository-root ``.env`` when the variable is not already set
    (same path ``Settings`` uses), so ``python -m app.db.seed`` from
    ``backend/`` works without exporting vars by hand.
    """
    value = os.environ.get("QAEGIS_DEV_SEED_PASSWORD", "").strip()
    if not value:
        from app.config import ENV_FILE

        if ENV_FILE.is_file():
            for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
                stripped = line.strip()
                if not stripped or stripped.startswith("#") or "=" not in stripped:
                    continue
                key, _, raw = stripped.partition("=")
                if key.strip() == "QAEGIS_DEV_SEED_PASSWORD":
                    value = raw.strip().strip('"').strip("'")
                    break
    if not value:
        raise RuntimeError(
            "QAEGIS_DEV_SEED_PASSWORD is not set. Add it to the repository-root "
            ".env (see .env.example), then re-run `python -m app.db.seed`."
        )
    if len(value) < 8:
        raise RuntimeError("QAEGIS_DEV_SEED_PASSWORD must be at least 8 characters.")
    return value


def dev_email(role: UserRole) -> str:
    """Return the seeded account address for ``role``."""
    return f"{role.value}@{DEV_EMAIL_DOMAIN}"


def dev_display_name(role: UserRole) -> str:
    """Return a human-readable name that says plainly what the account is."""
    return f"Dev {role.value.replace('_', ' ').title()} (seeded)"


def seed_development_users(
    session: Session, *, password: str | None = None
) -> dict[UserRole, str]:
    """Ensure one seeded user exists per role, with a password hash."""
    plain = password if password is not None else resolve_dev_password()
    password_hash = hash_password(plain)
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
    plain = resolve_dev_password()
    with session_scope() as session:
        seeded = seed_development_users(session, password=plain)
    print("password: (from QAEGIS_DEV_SEED_PASSWORD)")
    for role, email in seeded.items():
        print(f"{role.value:20} {email}")


if __name__ == "__main__":  # pragma: no cover
    main()
