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
    """Runtime settings."""

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

    # Event bus, SPEC.md 3.1 / 2.3. Redis Streams (decided 2026-09-14).
    # Optional: publish becomes a validated no-op when unset so CI smoke and
    # unit tests without Redis still import the app.
    redis_url: str | None = None
    # PEM CA for ``rediss://`` (compose mounts infra/certs/ca.crt).
    redis_ssl_ca_certs: str | None = None

    # FR-2 scheduled recompute interval in seconds. 0 disables the in-process
    # scheduler tick (tests, CI). Triggers via the bus still work.
    risk_recompute_interval_seconds: int = Field(default=300, ge=0)

    # Transactional outbox relay, SPEC.md 3.1. Every domain write persists its
    # events to the ``event_outbox`` table in the same transaction; this relay
    # drains pending rows to Redis Streams. Durability lives in the table, not in
    # process memory, so an event committed to the database is delivered even if
    # the process dies before publishing.
    #
    # Poll interval in seconds between relay drains. 0 disables the background
    # relay thread (tests / CI drive ``drain_once`` directly). A committed row is
    # still published promptly via the after-commit nudge when the thread runs.
    outbox_relay_interval_seconds: float = Field(default=2.0, ge=0.0, le=3600.0)
    # Rows claimed per drain. FOR UPDATE SKIP LOCKED means several relay workers
    # can run without double-publishing, so this bounds one worker's batch.
    outbox_relay_batch_size: int = Field(default=100, ge=1, le=1000)
    # Publish attempts before a row is dead-lettered (status='dead'). The row is
    # retained for inspection and manual requeue, never dropped.
    outbox_max_attempts: int = Field(default=8, ge=1, le=100)
    # Exponential backoff base, in seconds: delay = base * 2**(attempts-1),
    # capped at ``outbox_retry_cap_seconds``.
    outbox_retry_base_seconds: float = Field(default=2.0, gt=0.0, le=3600.0)
    outbox_retry_cap_seconds: float = Field(default=300.0, gt=0.0, le=86400.0)

    # AES wrapping key for document DEKs, SPEC.md Section 6 / NG5.
    # Base64url-encoded 32-byte key. Optional until encrypt is invoked.
    crypto_master_key: str | None = None

    # Comma-separated browser origins for CORS (frontend local/HTTPS local).
    cors_origins: str = (
        "http://127.0.0.1:3000,http://localhost:3000,"
        "https://127.0.0.1:3443,https://localhost:3443"
    )

    # Local JWT auth. Required for login; tests set a dummy secret.
    jwt_secret: str | None = None
    jwt_expire_minutes: int = Field(default=480, ge=5, le=60 * 24 * 7)

    # When true, X-Q-AEGIS-Actor-Role is accepted as a DEV-ONLY identity bypass.
    # Default false: opt in explicitly via AUTH_DEV_HEADER_BYPASS=true in local
    # .env / CI. Never enable in a shared environment.
    auth_dev_header_bypass: bool = False

    # Uploaded document bytes on local disk (not object storage this phase).
    document_storage_dir: str = "data/documents"
    upload_max_bytes: int = Field(default=50 * 1024 * 1024, ge=1024)

    # Knowledge graph, SPEC.md 3.11 / PRD FR-10. Optional: graph routes return
    # 503 when unset so CI smoke does not require Neo4j.
    qaegis_neo4j_uri: str | None = None
    qaegis_neo4j_user: str | None = None
    qaegis_neo4j_password: str | None = None
    # PEM CA for bolt+s:// (local compose). Optional when using bolt+ssc://.
    qaegis_neo4j_ssl_ca_certs: str | None = None

    # RAG embeddings, SPEC.md 3.12 / FR-11.
    # Backend: "fastembed" (real transformer embeddings, production default) or
    # "deterministic" (hash-based, non-semantic; tests / air-gapped smoke only).
    rag_embedding_backend: str = "fastembed"
    # fastembed model id. Default is a strong CPU-deployable retrieval model.
    # Its native dimension MUST equal rag_embedding_dims and the rag_chunks
    # pgvector column width.
    rag_embedding_model: str = "BAAI/bge-large-en-v1.5"
    # Directory fastembed loads model weights from. When set (the Docker image
    # bakes the model and points here via RAG_EMBEDDING_CACHE_DIR), fastembed
    # uses the pre-downloaded weights and never reaches the network. Unset on a
    # dev host means fastembed's default cache (downloads once, then offline).
    rag_embedding_cache_dir: str | None = None
    # Embedding width. Must match the model (bge-large-en-v1.5 = 1024) and the
    # rag_chunks.embedding vector(N) column.
    rag_embedding_dims: int = Field(default=1024, ge=8, le=2000)
    # Minimum cosine similarity a retrieved chunk must clear to count as
    # grounding evidence. This is the "refuse if ungrounded" gate (SPEC.md 3.12
    # / FR-11): when no stored chunk clears it, the pipeline retrieves nothing
    # and the Verifier refuses rather than answering from irrelevant records.
    # Only meaningful for the semantic ``fastembed`` backend; the deterministic
    # hash backend is non-semantic (tests / air-gapped smoke) and the floor is
    # disabled for it, see app/rag/store.py::effective_min_similarity.
    #
    # 0.57 is calibrated to the *actual* RAG grounding corpus, not guessed. This
    # pipeline grounds answers on a document's governance records — its inventory
    # snapshot and append-only audit-trail entries (see app/rag/ingest.py), NOT
    # the document body — so the floor must separate governance questions from
    # off-topic ones against THAT text. Probing the deployed bge-large-en-v1.5
    # over a fully-processed document's ingested chunks:
    #   - governance questions ("what policy decision / crypto profile / risk
    #     score / sensitivity label / audit history?") scored 0.635-0.725;
    #   - off-topic questions ("boiling point of liquid helium?", "capital of
    #     Australia?", "reverse a linked list in Python?") scored 0.343-0.509.
    # 0.57 sits in the separating band (off-topic ceiling 0.509, grounded floor
    # 0.635), ~0.06 margin each side. The earlier 0.30 default — and a first
    # mis-calibrated 0.46 probed against document *body* text the RAG never
    # ingests — sat below the off-topic cluster, so the gate never fired and was
    # cosmetic. Raise toward 0.60 to refuse more aggressively; absolute cosine
    # scale is somewhat document/length-dependent, so tune per corpus via
    # RAG_MIN_SIMILARITY. See docs/decisions.md 2026-09-24.
    rag_min_similarity: float = Field(default=0.57, ge=0.0, le=1.0)

    # Sensitivity classifier, SPEC.md 3.2.
    # A classification scoring below this threshold is escalated to the more
    # sensitive label. Load-bearing for the system's security posture, see
    # app/classifier/stub_classifier.py.
    classifier_confidence_threshold: float = Field(default=0.60, ge=0.0, le=1.0)
    # Path to a trained classifier artifact (produced by
    # app/classifier/training.py). When set and the file exists, the runtime
    # loads the model and the keyword rules become an escalation-only override;
    # when unset or missing, the classifier falls back to the keyword engine.
    # The trained model predicts only the three markings present in the training
    # corpus (PUBLIC/CONFIDENTIAL/RESTRICTED); INTERNAL is a policy-layer tier,
    # never an ML output. See docs/classifier-dataset.md.
    classifier_model_path: str | None = None

    # Five-agent scoring, SPEC.md 3.4 / FR-3.
    # Backend: "anthropic" (real Claude scoring; each agent's model, prompt, and
    # response are recorded in the audit) or "deterministic" (the reviewable
    # heuristic scorers). Default is deterministic so the app runs without
    # credentials; set anthropic + AGENT_LLM_API_KEY to activate real agents.
    agent_llm_backend: str = "deterministic"
    agent_llm_model: str = "claude-opus-4-8"
    agent_llm_api_key: str | None = None
    # Optional override for Anthropic-compatible gateways/proxies.
    agent_llm_base_url: str | None = None
    agent_llm_max_tokens: int = Field(default=512, ge=64, le=4096)
    agent_llm_timeout_seconds: float = Field(default=20.0, gt=0, le=120)
    # Extra CA bundle (PEM path) to trust for the agent LLM endpoint ONLY, on top
    # of the public roots. Set this when the endpoint is reached through a
    # corporate TLS-inspection proxy (e.g. Sophos/Zscaler) that re-signs traffic
    # with a private CA the public bundle does not contain. When set, the pedantic
    # VERIFY_X509_STRICT check (Python 3.13 default) is relaxed for this client
    # only, since interception CAs frequently ship a non-critical basicConstraints
    # extension; hostname and chain verification stay on. Scoped to the LLM client,
    # so datastore and other outbound TLS are unaffected.
    agent_llm_ca_bundle: str | None = None

    def cors_origin_list(self) -> list[str]:
        """Parse ``cors_origins`` into a list of non-empty origins."""
        return [part.strip() for part in self.cors_origins.split(",") if part.strip()]

    #: Environments where the forgeable X-Q-AEGIS-Actor-Role header may act as an
    #: identity bypass. Anything else (staging, production) must use real JWTs.
    _DEV_BYPASS_ENVS = frozenset({"local", "dev", "development", "test", "ci"})

    def dev_header_bypass_allowed(self) -> bool:
        """Whether the dev role-header bypass is actually honored.

        Defence in depth: even if ``AUTH_DEV_HEADER_BYPASS`` is left true, a
        non-local ``APP_ENV`` disables it, so a flag that leaks into staging or
        production cannot authenticate anyone. Callers must gate the bypass on
        this method, never on the raw flag.
        """
        return (
            self.auth_dev_header_bypass
            and self.app_env.strip().lower() in self._DEV_BYPASS_ENVS
        )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide settings singleton.

    Cached so that a config read is not repeated per request, and so tests can
    clear the cache to inject different values.
    """
    return Settings()
