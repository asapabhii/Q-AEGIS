"""FastAPI application entry point.

Run locally with::

    cd backend && uvicorn app.main:app --reload

TLS is required in transit everywhere per ``AGENTS.md``, including local
services. Uvicorn is run here without TLS because termination is handled at the
edge; wiring TLS is an infrastructure task and is called out as outstanding in
``infra/docker-compose.yml``. Do not read this file's silence on TLS as the
requirement being met.
"""

from fastapi import FastAPI

from app import __version__
from app.api import api_router


def create_app() -> FastAPI:
    """Build and configure the FastAPI application.

    A factory rather than a module-level singleton so tests can construct an
    isolated instance, and so configuration can be varied per instance without
    import-time side effects.
    """
    application = FastAPI(
        title="Q-AEGIS Shield",
        version=__version__,
        summary=(
            "Sensitivity classification, continuous risk scoring, crypto-agile "
            "protection, and tamper-evident audit logging."
        ),
        description=(
            "Phase 3 start. Live endpoints are the health check, document "
            "registration, the classifier stub, manual overrides, "
            "audit-chain verification, contextual risk scoring, the policy "
            "gate (persisted facts), trust-score consensus, and "
            "crypto-profile persist. See SPEC.md Section 7 for the full "
            "build order."
        ),
    )
    application.include_router(api_router)
    return application


app = create_app()
