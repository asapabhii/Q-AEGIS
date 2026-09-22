"""Asynchronous crypto reselection on trust change, ``SPEC.md`` 3.7 / ``PRD.md`` FR-6.

The synchronous pipeline (:func:`app.risk_engine.pipeline.run_full_assessment`)
selects and stores a protection profile in the same transaction that writes the
trust score. But a trust score can also be written on its own via
``POST /api/v1/trust-scores`` (``SPEC.md`` 3.5), which does not touch crypto. That
path publishes ``trust.updated``; this module is the consumer side that turns the
signal into a new ``crypto_profiles`` row when the protection band actually changes.

Idempotent by ``trust_score_id``: if a profile already exists for the trust score
(because the pipeline produced it, or because the event was redelivered), no new
row is written. A trust change that lands in the same band as the document's most
recent profile also writes nothing — reselection records a change, not a heartbeat.

SECURITY CAVEAT: liboqs is NOT independently audited, and OQS-OpenSSL is documented
by its own maintainers as development and interop-testing only, not
production-supported. Do not claim audited-grade or FIPS-certified guarantees that
the library does not back up.
"""

from __future__ import annotations

import logging
from uuid import UUID

from sqlalchemy.orm import Session

from app.crypto.selector import select_crypto_profile
from app.db.enums import AuditEventType
from app.db.models import CryptoProfile
from app.db.repositories import audit as audit_repo
from app.db.repositories import crypto as crypto_repo
from app.db.repositories import trust as trust_repo
from app.db.session import session_scope

logger = logging.getLogger(__name__)


def reselect_for_trust_score(
    session: Session, *, trust_score_id: UUID
) -> CryptoProfile | None:
    """Append a new protection profile if the trust score moved to a new band.

    Does not commit; the caller owns the transaction.

    Returns the new :class:`CryptoProfile` row, or ``None`` when nothing was
    written because: the trust score is unknown, a profile is already bound to it
    (pipeline already selected, or duplicate delivery), or the newly selected band
    equals the document's most recent profile.
    """
    trust = trust_repo.get_trust_score(session, trust_score_id)
    if trust is None:
        logger.warning(
            "trust.updated for unknown trust_score_id=%s; skipping reselect",
            trust_score_id,
        )
        return None

    if crypto_repo.exists_for_trust_score(session, trust_score_id):
        # The synchronous pipeline already produced a profile for this trust
        # score, or this event was redelivered. Either way, nothing to do.
        return None

    profile_type = select_crypto_profile(float(trust.consensus_value))
    latest = crypto_repo.latest_for_document(session, trust.document_id)
    if latest is not None and latest.profile_type == profile_type:
        # Same band as the current protection. Reselection records a change, not
        # a no-op restatement, so no append and no audit noise.
        return None

    profile_row = crypto_repo.append_profile(
        session,
        document_id=trust.document_id,
        trust_score_id=trust_score_id,
        profile_type=profile_type,
    )
    audit_repo.append_entry(
        session,
        event_type=AuditEventType.CRYPTO_PROFILE_SELECTED.value,
        document_id=trust.document_id,
        # No human actor: this selection is driven by the bus, like a scheduled
        # recompute (see app.risk_engine.recompute).
        actor_id=None,
        payload=crypto_repo.profile_selected_audit_payload(
            document_id=trust.document_id,
            trust_score_id=trust_score_id,
            crypto_profile_id=profile_row.id,
            profile_type=profile_type,
            consensus_value=trust.consensus_value,
            consensus_version=trust.consensus_version,
        ),
    )
    logger.info(
        "reselected crypto profile %s for document %s (trust_score_id=%s)",
        profile_type.value,
        trust.document_id,
        trust_score_id,
    )
    return profile_row


def reselect_from_trust_updated_payload(payload: dict[str, object]) -> None:
    """Open a session and reselect crypto from a validated ``trust.updated`` body.

    Used by the Redis Streams consumer. Opens its own session and commits, like
    :func:`app.risk_engine.recompute.run_scheduled_recompute`.
    """
    trust_score_id = UUID(str(payload["trust_score_id"]))
    with session_scope() as session:
        reselect_for_trust_score(session, trust_score_id=trust_score_id)
