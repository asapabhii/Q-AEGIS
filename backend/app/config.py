"""Application configuration, loaded from the environment.

Secrets are read from the environment only, never hardcoded, per ``AGENTS.md``
security rules. ``.env`` is gitignored; ``.env.example`` documents the shape of
the file with dummy values.

Key management this phase is environment-configured secrets rather than a
hardware security module. See ``PRD.md`` Non-Goal NG5 and ``SPEC.md`` Section 6
under "Key management this phase". Do not describe this as hardware-backed.
"""

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings.

    Phase 1 deliberately does not read database or broker credentials, because
    no module wires them yet. Adding them here before a consumer exists would
    imply a connection this build does not make.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "local"
    log_level: str = "INFO"

    # Sensitivity classifier, SPEC.md 3.2.
    # A classification scoring below this threshold is escalated to the more
    # sensitive label. Load-bearing for the system's security posture, see
    # app/classifier/stub_classifier.py.
    classifier_confidence_threshold: float = Field(default=0.60, ge=0.0, le=1.0)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton.

    Cached so that a config read is not repeated per request, and so tests can
    clear the cache to inject different values.
    """
    return Settings()
