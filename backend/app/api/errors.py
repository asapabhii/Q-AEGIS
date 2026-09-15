"""Global exception handlers for the API boundary.

Every unhandled failure leaves this module as a JSON ``{"detail": ...}``
response, never a Starlette plain-text page and never a traceback. The
traceback is logged server-side with the request path so operators can
diagnose without leaking internals to callers.

Deliberately unchanged here: ``HTTPException`` details stay exactly as each
route raised them (tests and the frontend match on those strings), and
request-validation failures keep FastAPI's default ``{"detail": [...]}``
shape, which the frontend already parses.
"""

import logging

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("q-aegis.api.errors")


class ErrorResponse(BaseModel):
    """Sanitized error envelope for failures with no safe detail to share."""

    model_config = {"extra": "forbid"}

    detail: str


async def _unhandled_exception_handler(
    request: Request, exc: Exception
) -> JSONResponse:
    """Log the traceback server-side; send a generic 500 to the caller."""
    logger.exception("Unhandled exception for %s %s", request.method, request.url.path)
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=jsonable_encoder(ErrorResponse(detail="Internal server error.")),
    )


async def _validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Keep FastAPI's 422 shape; add a one-line server-side log."""
    logger.warning(
        "Request validation failed for %s %s: %s",
        request.method,
        request.url.path,
        exc.errors(),
    )
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content=jsonable_encoder({"detail": exc.errors()}),
    )


async def _http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """Pass route-raised HTTP errors through unchanged, with a log line."""
    level = logger.error if exc.status_code >= 500 else logger.warning
    level(
        "HTTP %s for %s %s: %s",
        exc.status_code,
        request.method,
        request.url.path,
        exc.detail,
    )
    return JSONResponse(
        status_code=exc.status_code,
        content=jsonable_encoder({"detail": exc.detail}),
        headers=exc.headers,
    )


def register_error_handlers(application: FastAPI) -> None:
    """Attach the boundary handlers. Called once from :func:`app.main.create_app`."""
    application.add_exception_handler(StarletteHTTPException, _http_exception_handler)
    application.add_exception_handler(
        RequestValidationError, _validation_exception_handler
    )
    application.add_exception_handler(Exception, _unhandled_exception_handler)
