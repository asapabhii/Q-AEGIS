"""Read and write ``users``."""

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.enums import UserRole
from app.db.models import User


def create_user(
    session: Session,
    *,
    name: str,
    email: str,
    role: UserRole,
    password_hash: str | None = None,
) -> User:
    """Create a user row and return it, without committing."""
    user = User(
        name=name,
        email=email,
        role=role,
        password_hash=password_hash,
    )
    session.add(user)
    session.flush()
    return user


def find_by_email(session: Session, email: str) -> User | None:
    """Return the user with this email, or ``None``.

    ``email`` is unique, so this is at most one row.
    """
    return session.scalars(select(User).where(User.email == email)).one_or_none()


def first_by_role(session: Session, role: UserRole) -> User | None:
    """Return one user holding ``role``, or ``None`` if nobody does.

    Ordered by ``created_at`` then ``id`` so the answer is stable between calls
    rather than depending on physical row order. Used by the Phase 1 identity stub
    in :mod:`app.api.deps` to attach a real ``users`` row to a request that only
    presented a role. Real authentication resolves a specific user instead, at
    which point this function stops being an identity mechanism and goes back to
    being an ordinary query.
    """
    return session.scalars(
        select(User)
        .where(User.role == role)
        .order_by(User.created_at.asc(), User.id.asc())
        .limit(1)
    ).one_or_none()
