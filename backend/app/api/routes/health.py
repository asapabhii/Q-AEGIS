"""Health-check endpoint.

Deliberately unauthenticated, unlike every other endpoint. A liveness probe is
consumed by the container runtime and load balancer before any user identity
exists, so requiring a role here would make the service unmonitorable. The
tradeoff is bounded by the response containing no runtime detail an unauthorized
caller could use: no dependency status, no configuration, no version of anything
but this service.
"""

from typing import Literal

from fastapi import APIRouter
from pydantic import BaseModel

from app import __version__

router = APIRouter(tags=["health"])


class HealthResponse(BaseModel):
    """Liveness response.

    Reports only that the process is up and serving. It does NOT check
    Postgres, Redis, or Neo4j: Phase 1 wires none of them, and reporting
    ``"ok"`` for dependencies this build never contacts would be a false
    signal. A readiness endpoint that genuinely checks each dependency belongs
    with the module that first connects to one.
    """

    status: Literal["ok"]
    service: str
    version: str


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="Liveness check",
)
def health() -> HealthResponse:
    """Return service liveness."""
    return HealthResponse(
        status="ok", service="q-aegis-shield-backend", version=__version__
    )
