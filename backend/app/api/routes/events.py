"""Server-sent events for near-real-time dashboard updates.

``GET /api/v1/events/stream`` pushes Redis Stream bus events when
``REDIS_URL`` is set, otherwise heartbeats so the client can poll inventory.
Clients should use ``fetch`` (not bare ``EventSource``) so ``Authorization``
headers work.
"""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import APIRouter, Header, Request
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select

from app.api.deps import ACTOR_ROLE_HEADER, authenticate_user
from app.config import get_settings
from app.db.enums import UserRole
from app.db.models import Document
from app.db.session import session_scope
from app.event_bus.publisher import STREAM_KEY, is_bus_configured

logger = logging.getLogger(__name__)

router = APIRouter(tags=["events"])

_STREAM_ROLES = frozenset(
    {
        UserRole.SECURITY_ADMIN,
        UserRole.SECURITY_ANALYST,
        UserRole.AUDITOR,
        UserRole.CISO,
        UserRole.ENGINEER,
    }
)


def _authorize(
    authorization: str | None,
    actor_role: str | None,
) -> UserRole:
    with session_scope() as session:
        user = authenticate_user(
            session, authorization=authorization, actor_role=actor_role
        )
        if user.role not in _STREAM_ROLES:
            from fastapi import HTTPException, status

            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Caller role is not permitted to perform this action.",
            )
        return user.role


async def _redis_events(last_id: str) -> AsyncIterator[str]:
    """Yield SSE frames from Redis Streams ``XREAD``."""
    import redis

    settings = get_settings()
    client = redis.Redis.from_url(settings.redis_url, decode_responses=True)
    cursor = last_id
    try:
        while True:
            rows = await asyncio.to_thread(client.xread, {STREAM_KEY: cursor}, 10, 5000)
            if not rows:
                yield "event: ping\ndata: {}\n\n"
                continue
            for _stream, messages in rows:
                for msg_id, fields in messages:
                    cursor = msg_id
                    payload = {
                        "id": msg_id,
                        "event_type": fields.get("event_type"),
                        "payload": json.loads(fields.get("payload") or "{}"),
                        "occurred_at": fields.get("occurred_at"),
                    }
                    yield (
                        "event: bus\n" f"data: {json.dumps(payload, default=str)}\n\n"
                    )
    finally:
        client.close()


async def _poll_inventory() -> AsyncIterator[str]:
    """Fallback when Redis is unset: emit inventory fingerprint changes."""
    last_fingerprint: str | None = None
    while True:
        with session_scope() as session:
            count = session.scalar(select(func.count()).select_from(Document)) or 0
            newest = session.scalar(select(func.max(Document.uploaded_at)))
            fingerprint = f"{count}:{newest.isoformat() if newest else ''}"
        if fingerprint != last_fingerprint:
            last_fingerprint = fingerprint
            body = {"kind": "inventory_changed", "fingerprint": fingerprint}
            yield f"event: inventory\ndata: {json.dumps(body)}\n\n"
        else:
            yield "event: ping\ndata: {}\n\n"
        await asyncio.sleep(3)


@router.get("/events/stream", summary="SSE stream of bus / inventory updates")
async def events_stream(
    request: Request,
    authorization: Annotated[str | None, Header()] = None,
    actor_role: Annotated[str | None, Header(alias=ACTOR_ROLE_HEADER)] = None,
    last_event_id: Annotated[str | None, Header(alias="Last-Event-ID")] = None,
) -> StreamingResponse:
    """Stream server-sent events for dashboard live refresh."""
    _authorize(authorization, actor_role)
    start_id = last_event_id or "$"

    async def generate() -> AsyncIterator[str]:
        yield "event: ready\ndata: {}\n\n"
        source = _redis_events(start_id) if is_bus_configured() else _poll_inventory()
        async for frame in source:
            if await request.is_disconnected():
                break
            yield frame

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
