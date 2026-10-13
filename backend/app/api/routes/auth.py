"""Login and current-user endpoints for local JWT auth."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Header, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from app.api.deps import ACTOR_ROLE_HEADER, DbSession, authenticate_user
from app.auth.security import TOKEN_TYPE, create_access_token, verify_password
from app.config import get_settings
from app.db.enums import UserRole
from app.db.repositories import identity

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Plain str: seeded accounts use ``*.dev.qaegis.local``, which EmailStr
    # rejects as a reserved TLD. Format is still checked lightly below.
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=200)


class TokenResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    access_token: str
    token_type: str = TOKEN_TYPE
    user_id: UUID
    email: str
    role: UserRole
    name: str


class MeResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: UUID
    email: str
    role: UserRole
    name: str
    auth_mode: str


@router.post("/login", response_model=TokenResponse)
def login(request: LoginRequest, session: DbSession) -> TokenResponse:
    """Exchange email/password for a JWT access token."""
    if not get_settings().jwt_secret:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="JWT_SECRET is not configured.",
        )
    email = request.email.strip().lower()
    if "@" not in email or email.startswith("@") or email.endswith("@"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail="email must look like an address.",
        )
    user = identity.find_by_email(session, email)
    if user is None or not user.password_hash:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    if not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password.",
        )
    token = create_access_token(user_id=user.id, role=user.role.value, email=user.email)
    return TokenResponse(
        access_token=token,
        user_id=user.id,
        email=user.email,
        role=user.role,
        name=user.name,
    )


@router.get("/me", response_model=MeResponse)
def me(
    session: DbSession,
    authorization: Annotated[str | None, Header()] = None,
    actor_role: Annotated[str | None, Header(alias=ACTOR_ROLE_HEADER)] = None,
) -> MeResponse:
    """Return the authenticated caller."""
    user = authenticate_user(
        session, authorization=authorization, actor_role=actor_role
    )
    mode = (
        "jwt"
        if authorization and authorization.lower().startswith("bearer")
        else "dev_header"
    )
    return MeResponse(
        id=user.id,
        email=user.email,
        role=user.role,
        name=user.name,
        auth_mode=mode,
    )
