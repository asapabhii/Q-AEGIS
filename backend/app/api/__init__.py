"""FastAPI routers and API-layer dependencies.

Per ``AGENTS.md``: Pydantic models for every request and response body, no raw
dicts crossing an API boundary, and every endpoint checks caller identity and
role server-side before acting.
"""

from app.api.router import API_V1_PREFIX, api_router

__all__ = ["API_V1_PREFIX", "api_router"]
