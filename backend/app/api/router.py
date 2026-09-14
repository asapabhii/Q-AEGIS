"""Top-level API router, aggregating every route module.

Routers are collected here rather than registered ad hoc in
:mod:`app.main`, so there is one place to see the service's full surface.
"""

from fastapi import APIRouter

from app.api.routes import (
    assessments,
    audit,
    classify,
    crypto,
    documents,
    graph,
    health,
    migration,
    overrides,
    policy,
    rag,
    risk,
    shred,
    summary,
    trust,
)

#: Version prefix for the whole API. Present from the first endpoint so that a
#: future breaking change can ship as ``/v2`` instead of requiring every client
#: to move at once.
API_V1_PREFIX = "/api/v1"

api_router = APIRouter(prefix=API_V1_PREFIX)
api_router.include_router(health.router)
api_router.include_router(documents.router)
api_router.include_router(classify.router)
api_router.include_router(overrides.router)
api_router.include_router(audit.router)
api_router.include_router(risk.router)
api_router.include_router(assessments.router)
api_router.include_router(policy.router)
api_router.include_router(trust.router)
api_router.include_router(crypto.router)
api_router.include_router(shred.router)
api_router.include_router(summary.router)
api_router.include_router(migration.router)
api_router.include_router(graph.router)
api_router.include_router(rag.router)
