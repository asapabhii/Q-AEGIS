"""Shared API dependencies: session + authorization.

Primary auth is JWT (``Authorization: Bearer``). When
``AUTH_DEV_HEADER_BYPASS`` is true, ``X-Q-AEGIS-Actor-Role`` remains a
dev-only identity bypass that maps to a seeded user. Disable the bypass
outside local/CI.
"""

from __future__ import annotations

from collections.abc import Iterator
from contextvars import ContextVar
from typing import Annotated, Callable
from uuid import UUID

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.security import decode_access_token
from app.config import get_settings
from app.db.enums import UserRole
from app.db.models import User
from app.db.repositories import identity
from app.db.session import session_scope

ACTOR_ROLE_HEADER = "X-Q-AEGIS-Actor-Role"

_current_user_id: ContextVar[UUID | None] = ContextVar(
    "qaegis_current_user_id", default=None
)


def get_db_session() -> Iterator[Session]:
    """Yield a session whose transaction spans the whole request."""
    with session_scope() as session:
        yield session


DbSession = Annotated[Session, Depends(get_db_session)]


def _user_from_bearer(session: Session, authorization: str | None) -> User | None:
    if authorization is None or not authorization.strip():
        return None
    scheme, _, token = authorization.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authorization must be Bearer <token>.",
        )
    try:
        payload = decode_access_token(token.strip())
        user_id = UUID(str(payload["sub"]))
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired access token.",
        ) from exc
    user = session.get(User, user_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token subject is not a known user.",
        )
    return user


def _user_from_dev_header(session: Session, actor_role: str | None) -> User | None:
    settings = get_settings()
    if not settings.auth_dev_header_bypass:
        return None
    if actor_role is None or not actor_role.strip():
        return None
    try:
        role = UserRole(actor_role.strip().lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unrecognized caller role.",
        ) from None
    user = identity.first_by_role(session, role)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"No user exists with role '{role.value}'. Seed accounts with "
                "`python -m app.db.seed`."
            ),
        )
    return user


def authenticate_user(
    session: Session,
    *,
    authorization: str | None,
    actor_role: str | None,
) -> User:
    """Resolve the caller via JWT, else optional dev header bypass."""
    user = _user_from_bearer(session, authorization)
    if user is None:
        user = _user_from_dev_header(session, actor_role)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=(
                "Authentication required. Send Authorization: Bearer <token>, "
                f"or enable AUTH_DEV_HEADER_BYPASS and send {ACTOR_ROLE_HEADER}."
            ),
        )
    return user


def require_role(*allowed: UserRole) -> Callable[..., UserRole]:
    """Admit callers whose role is in ``allowed`` (JWT or dev bypass)."""

    permitted = frozenset(allowed)

    def dependency(
        session: DbSession,
        authorization: Annotated[str | None, Header()] = None,
        actor_role: Annotated[str | None, Header(alias=ACTOR_ROLE_HEADER)] = None,
    ) -> UserRole:
        user = authenticate_user(
            session, authorization=authorization, actor_role=actor_role
        )
        if user.role not in permitted:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Caller role is not permitted to perform this action.",
            )
        _current_user_id.set(user.id)
        return user.role

    return dependency


def resolve_seeded_actor(session: Session, role: UserRole) -> User:
    """Return the authenticated user for this request, or the seeded role user.

    JWT path: returns the token subject. Dev header bypass: returns the seeded
    account for ``role`` (same as before).
    """
    current_id = _current_user_id.get()
    if current_id is not None:
        user = session.get(User, current_id)
        if user is not None:
            return user
    actor = identity.first_by_role(session, role)
    if actor is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"No user exists with role '{role.value}', so this request cannot "
                "be attributed to an actor. Seed the development accounts with "
                "`python -m app.db.seed` (see docs/LOCAL_DEV.md)."
            ),
        )
    return actor


RegisterDocumentCaller = Annotated[
    UserRole,
    Depends(require_role(UserRole.DATA_OWNER, UserRole.SECURITY_ADMIN)),
]

ClassifyCaller = Annotated[
    UserRole,
    Depends(
        require_role(
            UserRole.DATA_OWNER,
            UserRole.SECURITY_ANALYST,
            UserRole.SECURITY_ADMIN,
        )
    ),
]

RiskScoreCaller = Annotated[
    UserRole,
    Depends(require_role(UserRole.SECURITY_ANALYST, UserRole.SECURITY_ADMIN)),
]

PolicyRuleCaller = Annotated[
    UserRole,
    Depends(require_role(UserRole.COMPLIANCE_OFFICER)),
]

PolicyDecisionCaller = Annotated[
    UserRole,
    Depends(require_role(UserRole.COMPLIANCE_OFFICER, UserRole.SECURITY_ADMIN)),
]

TrustScoreCaller = Annotated[
    UserRole,
    Depends(require_role(UserRole.SECURITY_ANALYST, UserRole.SECURITY_ADMIN)),
]

CryptoProfileCaller = Annotated[
    UserRole,
    Depends(require_role(UserRole.SECURITY_ANALYST, UserRole.SECURITY_ADMIN)),
]

OverrideCaller = Annotated[
    UserRole,
    Depends(require_role(UserRole.SECURITY_ANALYST, UserRole.SECURITY_ADMIN)),
]

DocumentInventoryCaller = Annotated[
    UserRole,
    Depends(
        require_role(
            UserRole.SECURITY_ADMIN,
            UserRole.SECURITY_ANALYST,
            UserRole.AUDITOR,
            UserRole.CISO,
            UserRole.ENGINEER,
        )
    ),
]

#: Roles allowed to crypto-shred a document's keys, ``PRD.md`` FR-8.
#: Data Owners request erasure; Compliance Officers handle erasure requests;
#: Security Admins act across the fleet. Analysts and auditors do not shred.
ShredCaller = Annotated[
    UserRole,
    Depends(
        require_role(
            UserRole.DATA_OWNER,
            UserRole.COMPLIANCE_OFFICER,
            UserRole.SECURITY_ADMIN,
        )
    ),
]

#: Roles allowed to export one document's summary, ``PRD.md`` FR-16.
#: Data Owners and Security Admins. Auditors use FR-15; they do not export.
SummaryCaller = Annotated[
    UserRole,
    Depends(require_role(UserRole.DATA_OWNER, UserRole.SECURITY_ADMIN)),
]

#: Roles allowed to run migration ranking, ``PRD.md`` FR-9.
#: Security Admins own fleet protection upgrades. Compliance may observe
#: priority but does not author the schedule in v1.
MigrationCaller = Annotated[
    UserRole,
    Depends(require_role(UserRole.SECURITY_ADMIN)),
]

#: Roles allowed to query / seed the knowledge graph, ``PRD.md`` FR-10.
#: Security Analysts and Admins explore attack paths; CISO reviews posture;
#: Engineers inspect topology. Data owners and auditors use other screens.
GraphCaller = Annotated[
    UserRole,
    Depends(
        require_role(
            UserRole.SECURITY_ANALYST,
            UserRole.SECURITY_ADMIN,
            UserRole.CISO,
            UserRole.ENGINEER,
        )
    ),
]

#: Roles allowed to ask grounded RAG questions, ``PRD.md`` FR-11.
#: Security Analysts / Admins investigate events; Auditors verify answers
#: against records; CISO asks fleet questions. Data owners use FR-16 summary.
RagCaller = Annotated[
    UserRole,
    Depends(
        require_role(
            UserRole.SECURITY_ANALYST,
            UserRole.SECURITY_ADMIN,
            UserRole.AUDITOR,
            UserRole.CISO,
        )
    ),
]
