"""Scheduled and bus-driven contextual risk recomputes, ``SPEC.md`` 3.3 / FR-2.

Uses each document's latest ``context_snapshot`` (device and actor flags) with a
fresh ``accessed_at``. System ticks write audit rows with no human actor.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.enums import AuditEventType
from app.db.models import RiskScore
from app.db.repositories import audit as audit_repo
from app.db.repositories import risk as risk_repo
from app.db.session import session_scope
from app.risk_engine.scorer import ContextSnapshot, score

logger = logging.getLogger(__name__)


def snapshot_from_stored(
    raw: dict[str, object],
    *,
    accessed_at: datetime | None = None,
) -> ContextSnapshot:
    """Rebuild a :class:`ContextSnapshot` from a persisted JSON blob.

    When ``accessed_at`` is provided it replaces the stored timestamp (schedule
    ticks refresh wall-clock while keeping caller-asserted device flags).
    """
    stored_accessed = raw["accessed_at"]
    if not isinstance(stored_accessed, str):
        raise ValueError("context_snapshot.accessed_at must be an ISO string")
    when = accessed_at or datetime.fromisoformat(stored_accessed)
    if when.tzinfo is None:
        when = when.replace(tzinfo=timezone.utc)
    return ContextSnapshot(
        actor_user_id=UUID(str(raw["actor_user_id"])),
        device_id=str(raw["device_id"]),
        device_is_new=bool(raw["device_is_new"]),
        accessed_at=when,
        after_hours=bool(raw["after_hours"]),
    )


def document_ids_with_risk_scores(session: Session) -> list[UUID]:
    """Return every document that has at least one contextual risk row."""
    return list(session.scalars(select(RiskScore.document_id).distinct()).all())


def append_recomputed_score(
    session: Session,
    *,
    document_id: UUID,
    snapshot: ContextSnapshot,
    actor_id: UUID | None = None,
) -> RiskScore:
    """Score ``snapshot``, append the row, and write the audit entry."""
    result = score(snapshot)
    row = risk_repo.append_risk_score(session, document_id=document_id, result=result)
    audit_repo.append_entry(
        session,
        event_type=AuditEventType.RISK_SCORE_COMPUTED.value,
        document_id=document_id,
        actor_id=actor_id,
        payload=risk_repo.risk_score_audit_payload(
            document_id=document_id,
            result=result,
            risk_score_id=row.id,
        ),
    )
    return row


def recompute_document_from_latest(
    session: Session,
    document_id: UUID,
    *,
    accessed_at: datetime | None = None,
) -> RiskScore | None:
    """Recompute one document from its latest snapshot, or ``None`` if none."""
    latest = risk_repo.latest_for_document(session, document_id)
    if latest is None:
        return None
    snapshot = snapshot_from_stored(
        latest.context_snapshot,
        accessed_at=accessed_at or datetime.now(timezone.utc),
    )
    return append_recomputed_score(
        session,
        document_id=document_id,
        snapshot=snapshot,
        actor_id=None,
    )


def run_scheduled_recompute(*, now: datetime | None = None) -> int:
    """Recompute every document that already has a risk score.

    Opens its own session and commits. Returns the number of new risk rows.
    Safe to call from the in-process ticker when Redis is not configured, and
    from the stream consumer when a ``schedule.tick`` arrives.
    """
    tick_at = now or datetime.now(timezone.utc)
    written = 0
    with session_scope() as session:
        for document_id in document_ids_with_risk_scores(session):
            row = recompute_document_from_latest(
                session, document_id, accessed_at=tick_at
            )
            if row is not None:
                written += 1
    logger.info("scheduled risk recompute wrote %s row(s)", written)
    return written


def recompute_from_trigger_payload(payload: dict[str, object]) -> RiskScore | None:
    """Score one document from a validated ``risk.trigger`` payload.

    Used by the stream consumer when a trigger is published without going
    through ``POST /risk-triggers`` (which already scores synchronously).
    """
    document_id = UUID(str(payload["document_id"]))
    snapshot = ContextSnapshot(
        actor_user_id=UUID(str(payload["actor_user_id"])),
        device_id=str(payload["device_id"]),
        device_is_new=bool(payload["device_is_new"]),
        accessed_at=datetime.fromisoformat(str(payload["accessed_at"])),
        after_hours=bool(payload["after_hours"]),
    )
    with session_scope() as session:
        from app.db.repositories import documents as documents_repo

        if documents_repo.get_document(session, document_id) is None:
            logger.warning(
                "risk.trigger for unknown document_id=%s; skipping", document_id
            )
            return None
        return append_recomputed_score(
            session,
            document_id=document_id,
            snapshot=snapshot,
            actor_id=None,
        )
