"""FastAPI application entry point.

Run locally with::

    cd backend && uvicorn app.main:app --reload

TLS is required in transit everywhere per ``AGENTS.md``, including local
services. Uvicorn is run here without TLS because termination is handled at the
edge; wiring TLS is an infrastructure task and is called out as outstanding in
``infra/docker-compose.yml``. Do not read this file's silence on TLS as the
requirement being met.
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import api_router
from app.config import get_settings


@asynccontextmanager
async def _lifespan(_application: FastAPI) -> AsyncIterator[None]:
    """Start optional FR-2 scheduler; stop on shutdown."""
    from app.risk_engine.scheduler import start_risk_scheduler, stop_risk_scheduler

    start_risk_scheduler()
    try:
        yield
    finally:
        stop_risk_scheduler()


def create_app() -> FastAPI:
    """Build and configure the FastAPI application.

    A factory rather than a module-level singleton so tests can construct an
    isolated instance, and so configuration can be varied per instance without
    import-time side effects.
    """
    settings = get_settings()
    application = FastAPI(
        title="Q-AEGIS Shield",
        version=__version__,
        summary=(
            "Sensitivity classification, continuous risk scoring, crypto-agile "
            "protection, and tamper-evident audit logging."
        ),
        description=(
            "P0 pipeline: register/classify, contextual risk (scheduled and "
            "triggered via Redis Streams), LangGraph five-agent assessment, "
            "trust consensus, OPA policy gate, crypto profile selection and "
            "byte encryption, Merkle audit. See SPEC.md Section 7."
        ),
        lifespan=_lifespan,
    )
    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list(),
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    application.include_router(api_router)
    return application


app = create_app()
