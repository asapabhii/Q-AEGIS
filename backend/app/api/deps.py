"""Shared API dependencies: the database session and the authorization guard.

``AGENTS.md`` requires every endpoint to check caller identity and role
(``users.role``) server-side before acting, and never to rely on frontend UI
hiding as access control. This module is where that check lives.
"""

from collections.abc import Iterator
from typing import Annotated, Callable

from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session

from app.db.enums import UserRole
from app.db.models import User
from app.db.repositories import identity
from app.db.session import session_scope

#: Header carrying the caller's role in the Phase 1 STUB guard below.
ACTOR_ROLE_HEADER = "X-Q-AEGIS-Actor-Role"


def get_db_session() -> Iterator[Session]:
    """Yield a session whose transaction spans the whole request.

    One transaction per request is what makes "a decision and the audit entry
    proving it happened are atomic" true: the handler writes both, and either
    both commit here or neither does. A handler that raises, including one
    raising ``HTTPException`` for a 404, rolls back rather than leaving a partial
    write behind.
    """
    with session_scope() as session:
        yield session


DbSession = Annotated[Session, Depends(get_db_session)]


def _parse_role(raw: str | None) -> UserRole:
    """Resolve a raw header value to a :class:`UserRole`, failing closed.

    Raises:
        HTTPException: 401 when no role is presented, 403 when the presented role
            is not recognized. Both are refusals; there is no branch here that
            proceeds without a valid role.
    """
    if raw is None or not raw.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Missing {ACTOR_ROLE_HEADER} header; caller identity is required.",
        )
    try:
        return UserRole(raw.strip().lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unrecognized caller role.",
        ) from None


def require_role(*allowed: UserRole) -> Callable[..., UserRole]:
    """Build a dependency that admits only callers holding one of ``allowed``.

    THE IDENTITY PORTION OF THIS GUARD IS A STUB. It trusts a request header to
    state the caller's role, which a client can trivially forge. It is NOT
    authentication and must not be described as such.

    It exists in this form because this build has no session handling and no
    identity provider (``PRD.md`` NG3 defers external identity providers). The
    ``users`` table now exists, so a request can be attached to a real row via
    :func:`resolve_seeded_actor`, but the row is chosen by the claimed role rather
    than proven by a credential. The call site is real and the role-to-endpoint
    mapping is real; only the identity source is stubbed.

    REPLACE BEFORE ANY NON-LOCAL DEPLOYMENT. The replacement resolves the caller
    from an authenticated session or token and reads ``users.role`` from that
    user's row. When it lands, this docstring, the header constant, and
    :func:`resolve_seeded_actor` all go away. Deployment of any kind is out of
    scope this phase per ``PRD.md`` NG4.

    Behavior that is not stubbed and should be preserved by the replacement: the
    guard fails closed. Absent, blank, and unrecognized roles are refused, and an
    empty ``allowed`` set refuses everyone rather than admitting anyone.

    Args:
        *allowed: Roles permitted to call the endpoint.

    Returns:
        A FastAPI dependency yielding the caller's :class:`UserRole`.
    """
    permitted = frozenset(allowed)

    def dependency(
        actor_role: Annotated[str | None, Header(alias=ACTOR_ROLE_HEADER)] = None,
    ) -> UserRole:
        role = _parse_role(actor_role)
        if role not in permitted:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Caller role is not permitted to perform this action.",
            )
        return role

    return dependency


def resolve_seeded_actor(session: Session, role: UserRole) -> User:
    """Return the ``users`` row this request will be attributed to.

    PART OF THE PHASE 1 IDENTITY STUB, see :func:`require_role`. It resolves the
    claimed role to the development account seeded for it, so that writes which
    reference ``users.id`` (``documents.uploaded_by``, ``audit_log.actor_id``) have
    a real row to point at.

    Args:
        session: Active session.
        role: The role the caller presented and the guard admitted.

    Returns:
        The seeded :class:`~app.db.models.User` for that role.

    Raises:
        HTTPException: 503 when no user holds the role. Deliberately not a
            silently-created user: writing a row on the fly here would mean an
            unauthenticated request could populate the identity table, and a
            forged header would then always resolve to something. Failing tells
            the operator to run ``python -m app.db.seed``.
    """
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


#: Roles allowed to register a document, per ``PRD.md`` Section 5: Data Owners
#: upload documents, and Security Admins act across the whole document set.
RegisterDocumentCaller = Annotated[
    UserRole,
    Depends(require_role(UserRole.DATA_OWNER, UserRole.SECURITY_ADMIN)),
]

#: Roles allowed to submit a classification request, per ``PRD.md`` Section 5:
#: Data Owners upload documents, and Security Analysts and Admins review and
#: re-run classifications. Compliance Officers and Auditors are deliberately
#: excluded, neither persona's stated need involves submitting documents.
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

#: Roles allowed to trigger a contextual risk recompute, ``PRD.md`` FR-2.
#: Security Analysts recompute before an override (FR-12); Security Admins
#: recompute for the dashboard (FR-14). Compliance, CISO, data owners, and
#: auditors are excluded: their stated needs do not include firing this engine.
RiskScoreCaller = Annotated[
    UserRole,
    Depends(require_role(UserRole.SECURITY_ANALYST, UserRole.SECURITY_ADMIN)),
]

#: Roles allowed to author override rules, ``PRD.md`` FR-13. Compliance Officers
#: define hard rules the AI cannot bypass. Nobody else authors them.
PolicyRuleCaller = Annotated[
    UserRole,
    Depends(require_role(UserRole.COMPLIANCE_OFFICER)),
]

#: Roles allowed to trigger a policy-gate evaluation, ``PRD.md`` FR-5.
#: Compliance Officers check that a rule fires; Security Admins run it for
#: the dashboard. Analysts, owners, CISO, and auditors do not trigger the gate.
PolicyDecisionCaller = Annotated[
    UserRole,
    Depends(require_role(UserRole.COMPLIANCE_OFFICER, UserRole.SECURITY_ADMIN)),
]

#: Roles allowed to trigger a trust-score consensus, ``PRD.md`` FR-4.
#: Same allow-list as contextual risk: analysts recompute the assessment,
#: admins recompute for the dashboard. 3.4 has not landed, so this is the
#: write path for the five caller-asserted agent scores as well.
TrustScoreCaller = Annotated[
    UserRole,
    Depends(require_role(UserRole.SECURITY_ANALYST, UserRole.SECURITY_ADMIN)),
]

#: Roles allowed to persist a crypto-profile selection, ``PRD.md`` FR-6.
#: Same allow-list as the assessment chain (3.3, 3.5): analysts select after
#: scoring; admins select for the dashboard. This is the mapping, not
#: encryption of bytes.
CryptoProfileCaller = Annotated[
    UserRole,
    Depends(require_role(UserRole.SECURITY_ANALYST, UserRole.SECURITY_ADMIN)),
]

#: Roles allowed to persist a manual classification override, ``PRD.md`` FR-12.
#: Security Analysts own the override screen; Security Admins act across the
#: document set. Data Owners see the outcome (FR-16) but do not relabel.
#: Compliance authors rules (FR-13); they do not write this table.
OverrideCaller = Annotated[
    UserRole,
    Depends(require_role(UserRole.SECURITY_ANALYST, UserRole.SECURITY_ADMIN)),
]
