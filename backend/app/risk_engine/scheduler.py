"""Scheduled contextual-risk recomputes, ``SPEC.md`` 3.3 / ``PRD.md`` FR-2.

The in-process ticker is optional (``RISK_RECOMPUTE_INTERVAL_SECONDS``). When
the interval is ``0`` the ticker is disabled (CI, tests). Immediate triggers
still go through ``POST /risk-triggers`` and Redis Streams.
"""

from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone

from app.config import get_settings
from app.event_bus import EventType, publish_event

logger = logging.getLogger(__name__)

_stop = threading.Event()
_thread: threading.Thread | None = None


def _tick_once() -> None:
    """Publish a system-level schedule heartbeat for subscribers.

    Per-document snapshots still require actor/device facts; the heartbeat
    signals consumers to re-pull context and call ``POST /risk-scores``.
    """
    publish_event(
        EventType.RISK_TRIGGER,
        {
            "document_id": "00000000-0000-0000-0000-000000000000",
            "actor_user_id": "00000000-0000-0000-0000-000000000000",
            "device_id": "scheduler",
            "device_is_new": False,
            "after_hours": False,
            "accessed_at": datetime.now(timezone.utc).isoformat(),
            "scheduled": True,
        },
    )


def _loop() -> None:
    settings = get_settings()
    interval = settings.risk_recompute_interval_seconds
    while not _stop.wait(interval):
        try:
            _tick_once()
        except Exception:  # noqa: BLE001 - ticker must not kill the process
            logger.exception("scheduled risk recompute publish failed")


def start_risk_scheduler() -> None:
    """Start the background ticker if an interval is configured."""
    global _thread
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
    """Signal the ticker to stop (tests / shutdown)."""
    _stop.set()
