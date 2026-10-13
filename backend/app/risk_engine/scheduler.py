"""Scheduled contextual-risk recomputes, ``SPEC.md`` 3.3 / ``PRD.md`` FR-2.

The in-process ticker is optional (``RISK_RECOMPUTE_INTERVAL_SECONDS``). When
the interval is ``0`` the ticker is disabled (CI, tests). Immediate triggers
still go through ``POST /risk-triggers``.

When Redis is configured the ticker publishes ``schedule.tick`` and the stream
consumer performs the recompute. When Redis is unset the ticker calls
:func:`run_scheduled_recompute` directly so FR-2 scheduled scoring still works.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone

from app.config import get_settings
from app.event_bus.publisher import is_bus_configured, publish_event
from app.event_bus.schemas import EventType

logger = logging.getLogger(__name__)

_stop = threading.Event()
_thread: threading.Thread | None = None


def _tick_once() -> None:
    """Emit one schedule tick or recompute in-process when the bus is offline."""
    tick_at = datetime.now(timezone.utc)
    if is_bus_configured():
        publish_event(
            EventType.SCHEDULE_TICK,
            {
                "scheduled": True,
                "tick_at": tick_at.isoformat(),
            },
        )
        return

    from app.risk_engine.recompute import run_scheduled_recompute

    run_scheduled_recompute(now=tick_at)


def _loop() -> None:
    settings = get_settings()
    interval = settings.risk_recompute_interval_seconds
    while not _stop.wait(interval):
        try:
            _tick_once()
        except Exception:  # noqa: BLE001 - ticker must not kill the process
            logger.exception("scheduled risk recompute tick failed")


def start_risk_scheduler() -> None:
    """Start the background ticker and, when Redis is set, the stream consumer."""
    global _thread
    from app.event_bus.consumer import start_risk_consumer
    from app.event_bus.relay import start_outbox_relay

    start_risk_consumer()
    # Drain the transactional outbox to Redis. Independent of the ticker interval:
    # events are enqueued by request handlers regardless of scheduled recomputes,
    # so the relay must run whenever the bus is configured.
    start_outbox_relay()

    interval = get_settings().risk_recompute_interval_seconds
    if interval <= 0:
        logger.info("risk scheduler disabled (interval=%s)", interval)
        return
    if _thread is not None and _thread.is_alive():
        return
    _stop.clear()
    _thread = threading.Thread(target=_loop, name="risk-scheduler", daemon=True)
    _thread.start()
    logger.info("risk scheduler started (interval=%ss)", interval)


def stop_risk_scheduler() -> None:
    """Signal the ticker and consumer to stop (tests / shutdown)."""
    from app.event_bus.consumer import stop_risk_consumer
    from app.event_bus.relay import stop_outbox_relay

    _stop.set()
    stop_risk_consumer()
    stop_outbox_relay()
