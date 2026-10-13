"""Shared Redis client factory for TLS-aware local/dev connections."""

from __future__ import annotations

from typing import Any

from app.config import get_settings


def redis_from_settings(**extra: Any):
    """Build a Redis client from settings, attaching the local CA for ``rediss://``.

    Without ``REDIS_SSL_CA_CERTS`` (or ``SSL_CERT_FILE``), redis-py rejects the
    self-signed compose CA and the event bus dies while the HTTP app stays up.

    TLS verification is only ever relaxed for ``APP_ENV=local``, where the
    self-signed compose CA is expected. In any other environment a ``rediss://``
    URL with no CA configured is a misconfiguration that would otherwise silently
    disable certificate verification (a MITM opening); we fail closed instead and
    demand ``REDIS_SSL_CA_CERTS`` so the connection is actually authenticated.
    """
    import redis

    settings = get_settings()
    url = settings.redis_url
    if not url:
        raise RuntimeError("REDIS_URL is not configured")

    kwargs: dict[str, Any] = {"decode_responses": True, **extra}
    if url.startswith("rediss://"):
        ca = settings.redis_ssl_ca_certs
        if settings.app_env.strip().lower() == "local":
            # Local only: OpenSSL 3 rejects our self-signed compose CA when
            # keyUsage is missing, so accept it unverified to keep the bus up
            # until the certs are regenerated with proper CA extensions.
            kwargs.setdefault("ssl_cert_reqs", "none")
            kwargs.setdefault("ssl_check_hostname", False)
        elif ca:
            kwargs.setdefault("ssl_ca_certs", ca)
        else:
            # Non-local + no CA: fail closed rather than silently downgrade to
            # an unverified TLS connection (MITM risk).
            raise RuntimeError(
                "rediss:// requires REDIS_SSL_CA_CERTS outside APP_ENV=local; "
                "refusing to connect with certificate verification disabled"
            )
    return redis.Redis.from_url(url, **kwargs)
