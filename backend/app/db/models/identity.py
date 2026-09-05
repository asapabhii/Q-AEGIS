"""``users``, the identity table."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, created_timestamp, uuid_primary_key
from app.db.enums import UserRole
from app.db.types import USER_ROLE


class User(Base):
    """A person who acts on the system.

    ``role`` is the value every endpoint's server-side authorization check reads
    (``AGENTS.md``: never rely on frontend UI hiding as access control). Note that
    as of this build the API's identity source is still a stub trusting a request
    header, so a row here is not yet proof of an authenticated session. See
    :mod:`app.api.deps`.
    """

    __tablename__ = "users"

    id: Mapped[UUID] = uuid_primary_key()
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    role: Mapped[UserRole] = mapped_column(USER_ROLE, nullable=False)
    created_at: Mapped[datetime] = created_timestamp()
