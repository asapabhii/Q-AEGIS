"""The X-Q-AEGIS-Actor-Role dev bypass is confined to local-like environments.

Defence in depth for the auth model: even if ``AUTH_DEV_HEADER_BYPASS`` is left
true, a non-local ``APP_ENV`` must disable the forgeable header so it cannot
authenticate anyone in staging or production.
"""

from __future__ import annotations

import pytest
from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.api.deps import authenticate_user
from app.config import Settings, get_settings
from app.db.enums import UserRole
from app.db.models import User


def test_dev_bypass_allowed_only_in_local_like_envs() -> None:
    for env in ("local", "dev", "development", "test", "ci", "LOCAL"):
        settings = Settings(app_env=env, auth_dev_header_bypass=True)
        assert settings.dev_header_bypass_allowed() is True, env
    for env in ("production", "prod", "staging", "PRODUCTION", "prod-eu"):
        settings = Settings(app_env=env, auth_dev_header_bypass=True)
        assert settings.dev_header_bypass_allowed() is False, env


def test_dev_bypass_off_when_flag_false() -> None:
    settings = Settings(app_env="local", auth_dev_header_bypass=False)
    assert settings.dev_header_bypass_allowed() is False


def test_dev_header_authenticates_in_local(
    db_session: Session, seeded_users: dict[UserRole, User]
) -> None:
    # conftest sets APP_ENV default (local) + AUTH_DEV_HEADER_BYPASS=true.
    user = authenticate_user(
        db_session, authorization=None, actor_role=UserRole.SECURITY_ADMIN.value
    )
    assert user.role is UserRole.SECURITY_ADMIN


def test_dev_header_rejected_in_production(
    db_session: Session,
    seeded_users: dict[UserRole, User],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("APP_ENV", "production")
    get_settings.cache_clear()
    with pytest.raises(HTTPException) as exc:
        authenticate_user(
            db_session, authorization=None, actor_role=UserRole.SECURITY_ADMIN.value
        )
    assert exc.value.status_code == 401
