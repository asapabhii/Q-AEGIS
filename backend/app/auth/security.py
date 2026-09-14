"""JWT password hashing and token helpers.

Local email/password auth (not an external IdP). The forgeable
``X-Q-AEGIS-Actor-Role`` header remains available only when
``AUTH_DEV_HEADER_BYPASS`` is enabled.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import bcrypt
import jwt

from app.config import get_settings

ALGORITHM = "HS256"
TOKEN_TYPE = "bearer"


def hash_password(plain: str) -> str:
    """Hash a password with bcrypt."""
    return bcrypt.hashpw(plain.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain: str, password_hash: str) -> bool:
    """Return whether ``plain`` matches ``password_hash``."""
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(*, user_id: UUID, role: str, email: str) -> str:
    """Issue a signed JWT access token."""
    settings = get_settings()
    secret = settings.jwt_secret
    if not secret:
        raise RuntimeError("JWT_SECRET is not configured")
    now = datetime.now(timezone.utc)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "role": role,
        "email": email,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_expire_minutes)).timestamp()),
    }
    return jwt.encode(payload, secret, algorithm=ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate a JWT. Raises ``jwt.PyJWTError`` on failure."""
    settings = get_settings()
    secret = settings.jwt_secret
    if not secret:
        raise RuntimeError("JWT_SECRET is not configured")
    return jwt.decode(token, secret, algorithms=[ALGORITHM])
