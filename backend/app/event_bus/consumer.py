"""Redis Streams consumer for FR-2 schedule ticks and risk triggers.

When ``REDIS_URL`` is unset the consumer does not start. The in-process
scheduler falls back to calling :func:`run_scheduled_recompute` directly so
scheduled recomputes still run in local/CI environments without Redis.
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Any

from app.config import get_settings
from app.event_bus.client import redis_from_settings
from app.event_bus.publisher import STREAM_KEY, is_bus_configured, parse_stream_fields
from app.event_bus.schemas import EventType
from app.risk_engine.recompute import run_scheduled_recompute

logger = logging.getLogger(__name__)

GROUP_NAME = "qaegis-risk-recompute"
CONSUMER_NAME = "risk-worker-1"
BLOCK_MS = 2000

_stop = threading.Event()
_thread: threading.Thread | None = None


def _ensure_group(client: Any) -> None:
    try:
        client.xgroup_create(STREAM_KEY, GROUP_NAME, id="0", mkstream=True)
    except Exception as exc:  # noqa: BLE001 - BUSYGROUP is expected after first start
        if "BUSYGROUP" not in str(exc):
            raise


def _handle_envelope(envelope: Any) -> None:
    if envelope.event_type is EventType.SCHEDULE_TICK:
        tick_raw = envelope.payload["tick_at"]
        if isinstance(tick_raw, str):
            from datetime import datetime

            tick_at = datetime.fromisoformat(tick_raw)
        else:
            tick_at = tick_raw
        run_scheduled_recompute(now=tick_at)
        return
    # ``risk.trigger`` is scored synchronously by ``POST /risk-triggers``.
    # Other event types are ignored by this worker.


def _loop() -> None:
    if not get_settings().redis_url:
        return

    try:
        client = redis_from_settings()
    except ImportError:  # pragma: no cover
        logger.error("redis package missing; risk consumer cannot start")
        return

    try:
        _ensure_group(client)
        while not _stop.is_set():
            try:
                rows = client.xreadgroup(
                    GROUP_NAME,
                    CONSUMER_NAME,
                    {STREAM_KEY: ">"},
                    count=10,
                    block=BLOCK_MS,
                )
            except Exception:  # noqa: BLE001
                logger.exception("risk consumer xreadgroup failed")
                time.sleep(1)
                continue
            if not rows:
                continue
            for _stream, messages in rows:
                for entry_id, fields in messages:
                    try:
                        envelope = parse_stream_fields(fields)
                        _handle_envelope(envelope)
                        client.xack(STREAM_KEY, GROUP_NAME, entry_id)
                    except Exception:  # noqa: BLE001 - one bad entry must not kill loop
                        logger.exception("failed handling stream entry %s", entry_id)
    finally:
        client.close()


def start_risk_consumer() -> None:
    """Start the background stream consumer when Redis is configured."""
    global _thread
    if not is_bus_configured():
        logger.info("risk consumer disabled (REDIS_URL unset)")
        return
    if _thread is not None and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="risk-consumer", daemon=True)
    _thread.start()
    logger.info("risk consumer started (group=%s)", GROUP_NAME)


def stop_risk_consumer() -> None:
    """Signal the consumer to stop (tests / shutdown)."""
    _stop.set()
