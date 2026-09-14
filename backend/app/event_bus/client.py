"""Shared Redis client factory for TLS-aware local/dev connections."""

from __future__ import annotations

from typing import Any

from app.config import get_settings


def redis_from_settings(**extra: Any):
    """Build a Redis client from settings, attaching the local CA for ``rediss://``.

    Without ``REDIS_SSL_CA_CERTS`` (or ``SSL_CERT_FILE``), redis-py rejects the
    self-signed compose CA and the event bus dies while the HTTP app stays up.
    """
    import redis

    settings = get_settings()
    url = settings.redis_url
    if not url:
        raise RuntimeError("REDIS_URL is not configured")

    kwargs: dict[str, Any] = {"decode_responses": True, **extra}
    if url.startswith("rediss://"):
        ca = settings.redis_ssl_ca_certs
        # OpenSSL 3 rejects our local CA when keyUsage is missing on the CA
        # cert. Prefer verify-ca when the CA is correct; for APP_ENV=local
        # fall back to CERT_NONE so the bus still works until certs are
        # regenerated with proper CA extensions.
        if settings.app_env == "local":
            kwargs.setdefault("ssl_cert_reqs", "none")
            kwargs.setdefault("ssl_check_hostname", False)
        elif ca:
            kwargs.setdefault("ssl_ca_certs", ca)
        else:
            kwargs.setdefault("ssl_cert_reqs", "none")
            kwargs.setdefault("ssl_check_hostname", False)
    return redis.Redis.from_url(url, **kwargs)
