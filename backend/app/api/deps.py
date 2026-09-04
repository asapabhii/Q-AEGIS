"""Shared API dependencies, including the authorization guard.

``AGENTS.md`` requires every endpoint to check caller identity and role
(``users.role``) server-side before acting, and never to rely on frontend UI
hiding as access control. This module is where that check lives.
"""

from enum import Enum
from typing import Annotated, Callable

from fastapi import Depends, Header, HTTPException, status

#: Header carrying the caller's role in the Phase 1 STUB guard below.
ACTOR_ROLE_HEADER = "X-Q-AEGIS-Actor-Role"


class Role(str, Enum):
    """Caller roles, mirroring ``users.role`` and ``PRD.md`` Section 5's personas."""

    DATA_OWNER = "data_owner"
    SECURITY_ANALYST = "security_analyst"
    SECURITY_ADMIN = "security_admin"
    COMPLIANCE_OFFICER = "compliance_officer"
    AUDITOR = "auditor"


def _parse_role(raw: str | None) -> Role:
    """Resolve a raw header value to a :class:`Role`, failing closed.

    Raises:
        HTTPException: 401 when no role is presented, 403 when the presented
            role is not recognized. Both are refusals; there is no branch here
            that proceeds without a valid role.
    """
    if raw is None or not raw.strip():
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Missing {ACTOR_ROLE_HEADER} header; caller identity is required.",
        )
    try:
        return Role(raw.strip().lower())
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unrecognized caller role.",
        ) from None


def require_role(*allowed: Role) -> Callable[..., Role]:
    """Build a dependency that admits only callers holding one of ``allowed``.

    THE IDENTITY PORTION OF THIS GUARD IS A STUB. It trusts a request header to
    state the caller's role, which a client can trivially forge. It is NOT
    authentication and must not be described as such.

    It exists in this form because Phase 1 has no ``users`` table, no session
    handling, and no identity provider (``PRD.md`` NG3 defers external identity
    providers; ``SPEC.md`` Section 5's ``users`` table is unbuilt). The
    alternative was to ship the endpoint with no server-side check at all, which
    would have left the authorization call site missing entirely and made its
    later absence easy to overlook. The call site is real and the role-to-
    endpoint mapping is real; only the identity source is stubbed.

    REPLACE BEFORE ANY NON-LOCAL DEPLOYMENT. The replacement resolves the caller
    from an authenticated session or token and reads ``users.role`` from the
    database. When that lands, this docstring and the header constant go away.
    Deployment of any kind is out of scope this phase per ``PRD.md`` NG4.

    Behavior that is not stubbed and should be preserved by the replacement:
    the guard fails closed. Absent, blank, or unrecognized roles are refused,
    and an empty ``allowed`` set refuses everyone rather than admitting anyone.

    Args:
        *allowed: Roles permitted to call the endpoint.

    Returns:
        A FastAPI dependency yielding the caller's :class:`Role`.
    """
    permitted = frozenset(allowed)

    def dependency(
        actor_role: Annotated[str | None, Header(alias=ACTOR_ROLE_HEADER)] = None,
    ) -> Role:
        role = _parse_role(actor_role)
        if role not in permitted:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Caller role is not permitted to perform this action.",
            )
        return role

    return dependency


#: Roles allowed to submit a classification request, per ``PRD.md`` Section 5:
#: Data Owners upload documents, and Security Analysts and Admins review and
#: re-run classifications. Compliance Officers and Auditors are deliberately
#: excluded, neither persona's stated need involves submitting documents.
ClassifyCaller = Annotated[
    Role,
    Depends(
        require_role(
            Role.DATA_OWNER,
            Role.SECURITY_ANALYST,
            Role.SECURITY_ADMIN,
        )
    ),
]
