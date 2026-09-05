"""Application configuration, loaded from the environment.

Secrets are read from the environment only, never hardcoded, per ``AGENTS.md``
security rules. ``.env`` is gitignored; ``.env.example`` documents the shape of
the file with dummy values.

Key management this phase is environment-configured secrets rather than a
hardware security module. See ``PRD.md`` Non-Goal NG5 and ``SPEC.md`` Section 6
under "Key management this phase". Do not describe this as hardware-backed.
"""

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

#: Absolute path to the repository-root ``.env``.
#:
#: Absolute, not the bare relative ``".env"``, because a relative path is
#: resolved against the current working directory: the same process finds the
#: file when started from the repository root and silently finds nothing when
#: started from ``backend/``, which is where the documented ``uvicorn`` and
#: ``alembic`` commands are run from. The failure is quiet, every setting just
#: falls back to its default, so a database URL would read as "not configured"
#: on a machine where it is configured.
#:
#: One ``.env`` at the repository root is also what ``infra/docker-compose.yml``
#: reads, so the application and the containers cannot drift onto different
#: credentials. A missing file is not an error; every setting here has a default
#: or is optional.
ENV_FILE = Path(__file__).resolve().parents[2] / ".env"


class Settings(BaseSettings):
    """Runtime settings.

    Broker credentials are still absent deliberately: no module wires the event
    bus yet (``SPEC.md`` 3.1), and reading them here before a consumer exists
    would imply a connection this build does not make.
    """

    model_config = SettingsConfigDict(
        env_file=ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    app_env: str = "local"
    log_level: str = "INFO"

    # Data model, SPEC.md Section 5. Optional rather than required, and with no
    # default value, for two specific reasons:
    #
    #   - No default: a fallback like "postgresql+psycopg://localhost/qaegis"
    #     would embed credentials in source and, worse, would let a
    #     misconfigured process connect somewhere unintended instead of failing.
    #   - Optional: the liveness endpoint and the whole classifier module work
    #     without a database, and the Docker image's smoke test in CI starts the
    #     container with no database reachable. Making this required would turn
    #     "no DATABASE_URL" into an import-time crash for paths that never touch
    #     Postgres.
    #
    # Code that genuinely needs a connection calls
    # ``app.db.session.require_database_url()``, which fails loudly and names
    # this variable. Absence is never silently tolerated at the point of use.
    database_url: str | None = None

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
