"""Append to ``risk_scores``, ``SPEC.md`` 3.3, ``PRD.md`` FR-2.

Append only. There is no update function.
"""

from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import RiskScore
from app.risk_engine.scorer import RiskScoreResult

if TYPE_CHECKING:
    from app.agents.features import AccessFeatures

#: Upper bound on rows scanned per behavioural aggregate in
#: :func:`access_history`. Counts and the after-hours ratio are computed over
#: the most-recent window of matching ``risk_scores`` rows, so a single
#: assessment cannot trigger an unbounded scan as history grows. The signals are
#: thresholds and a ratio, not exact accounting, and any undercount at the
#: window edge makes an actor/device look *less* established — the fail-safe
#: direction (more protection), so the bound never trades away safety.
HISTORY_WINDOW = 1000


def get_risk_score(session: Session, risk_score_id: UUID) -> RiskScore | None:
    """Return one contextual risk row, or ``None`` if it was never written."""
    return session.scalars(
        select(RiskScore).where(RiskScore.id == risk_score_id)
    ).one_or_none()


def latest_for_document(session: Session, document_id: UUID) -> RiskScore | None:
    """Return the most recent contextual score for a document, if any.

    Ordered by ``computed_at`` then ``id``. Same tiebreak as classification:
    two rows in one transaction share a timestamp and still need an order.
    """
    return session.scalars(
        select(RiskScore)
        .where(RiskScore.document_id == document_id)
        .order_by(RiskScore.computed_at.desc(), RiskScore.id.desc())
        .limit(1)
    ).one_or_none()


def access_history(
    session: Session,
    *,
    actor_user_id: UUID,
    device_id: str,
    document_id: UUID,
) -> "AccessFeatures":
    """Build the frozen per-access behavioural bundle for the scoring agents.

    Reads only the append-only ``risk_scores`` history via its JSONB
    ``context_snapshot`` and returns an
    :class:`app.agents.features.AccessFeatures`. Every count EXCLUDES the current
    access: this runs BEFORE :func:`append_risk_score` writes the new row, so
    "prior" means strictly earlier accesses.

    ``actor_role`` and ``payload_byte_size`` are not history and are not set
    here; the pipeline layers them on (via :func:`dataclasses.replace`) from the
    authenticated actor and the plaintext it holds. This function performs no
    network or model work and must stay a cheap, request-thread query so the
    computed bundle can be frozen before the parallel fan-out.
    """
    # Deferred import: keep the db layer free of an import-time dependency on
    # the agents layer (mirrors graph.py deferring ContextSnapshot).
    from app.agents.features import AccessFeatures

    actor_key = str(actor_user_id)
    device_key = str(device_id)
    actor_col = RiskScore.context_snapshot["actor_user_id"].astext
    device_col = RiskScore.context_snapshot["device_id"].astext
    after_hours_col = RiskScore.context_snapshot["after_hours"].astext

    # Window of this actor's most-recent accesses. Totals and after-hours count
    # come from the SAME window so the ratio is internally consistent.
    actor_window = (
        select(
            after_hours_col.label("after_hours"),
            device_col.label("device_id"),
        )
        .where(actor_col == actor_key)
        .order_by(RiskScore.computed_at.desc(), RiskScore.id.desc())
        .limit(HISTORY_WINDOW)
        .subquery()
    )
    actor_prior = session.execute(
        select(func.count()).select_from(actor_window)
    ).scalar_one()
    actor_after_hours = session.execute(
        select(func.count())
        .select_from(actor_window)
        .where(actor_window.c.after_hours == "true")
    ).scalar_one()
    actor_device_prior = session.execute(
        select(func.count())
        .select_from(actor_window)
        .where(actor_window.c.device_id == device_key)
    ).scalar_one()

    # Distinct actors seen on this device (device sharing) over its own window.
    device_window = (
        select(actor_col.label("actor_user_id"))
        .where(device_col == device_key)
        .order_by(RiskScore.computed_at.desc(), RiskScore.id.desc())
        .limit(HISTORY_WINDOW)
        .subquery()
    )
    device_distinct_actors = session.execute(
        select(func.count(func.distinct(device_window.c.actor_user_id)))
    ).scalar_one()

    # Prior accesses to this document, and its most-recent prior risk value for
    # the contextual trend signal.
    doc_window = (
        select(RiskScore.id)
        .where(RiskScore.document_id == document_id)
        .order_by(RiskScore.computed_at.desc(), RiskScore.id.desc())
        .limit(HISTORY_WINDOW)
        .subquery()
    )
    document_prior = session.execute(
        select(func.count()).select_from(doc_window)
    ).scalar_one()
    latest = latest_for_document(session, document_id)
    document_prior_risk = None if latest is None else latest.risk_value

    return AccessFeatures(
        actor_prior_access_count=int(actor_prior),
        actor_device_prior_count=int(actor_device_prior),
        actor_after_hours_count=int(actor_after_hours),
        device_distinct_actor_count=int(device_distinct_actors),
        document_prior_access_count=int(document_prior),
        document_prior_risk_value=document_prior_risk,
    )


def append_risk_score(
    session: Session,
    *,
    document_id: UUID,
    result: RiskScoreResult,
) -> RiskScore:
    """Record one contextual scoring and return the row, without committing.

    ``risk_value`` is already a ``Decimal`` quantized to four places; it is not
    converted through ``float``.
    """
    row = RiskScore(
        document_id=document_id,
        risk_value=result.risk_value,
        model_version=result.model_version,
        context_snapshot=result.snapshot.as_json(),
    )
    session.add(row)
    session.flush()
    return row


def risk_score_audit_payload(
    *,
    document_id: UUID,
    result: RiskScoreResult,
    risk_score_id: UUID,
    reported_by_user_id: UUID | None = None,
    reported_by_role: str | None = None,
) -> dict[str, Any]:
    """Audit payload for one contextual scoring.

    JSON primitives only. Includes ``model_version`` so a stored score remains
    attributable after the weights change.

    The snapshot's ``actor_user_id`` is the *subject* of the access being scored.
    When the request was made by a different, authenticated principal (a
    third-party report), ``reported_by_user_id`` / ``reported_by_role`` record
    that reporter distinctly from the subject, so the record is self-describing
    about who reported whose access. For self-reported access the two coincide;
    for system-driven recomputes no reporter is supplied and the keys are
    omitted (the audit entry's ``actor_id`` still carries attribution).
    """
    payload: dict[str, Any] = {
        "risk_score_id": str(risk_score_id),
        "document_id": str(document_id),
        "risk_value": str(result.risk_value),
        "model_version": result.model_version,
    }
    payload.update(result.snapshot.as_json())
    if reported_by_user_id is not None:
        payload["reported_by_user_id"] = str(reported_by_user_id)
    if reported_by_role is not None:
        payload["reported_by_role"] = reported_by_role
    return payload
