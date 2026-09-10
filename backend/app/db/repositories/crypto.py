"""Append ``crypto_profiles``, ``SPEC.md`` 3.7, ``PRD.md`` FR-6.

Append only. There is no update function. Reselection is a new row.

SECURITY CAVEAT: liboqs is NOT independently audited, and OQS-OpenSSL is
documented by its own maintainers as development and interop-testing only, not
production-supported. Do not claim audited-grade or FIPS-certified guarantees
that the library does not back up.
"""

from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.crypto.selector import HYBRID_MAX, POST_QUANTUM_MAX
from app.db.enums import CryptoProfileType
from app.db.models import CryptoProfile


def latest_for_document(session: Session, document_id: UUID) -> CryptoProfile | None:
    """Return the most recent protection selection for a document, if any.

    Ordered by ``selected_at`` then ``id``. SECURITY CAVEAT: liboqs is not
    independently audited; this function only reads a stored profile type.
    """
    return session.scalars(
        select(CryptoProfile)
        .where(CryptoProfile.document_id == document_id)
        .order_by(CryptoProfile.selected_at.desc(), CryptoProfile.id.desc())
        .limit(1)
    ).one_or_none()


def append_profile(
    session: Session,
    *,
    document_id: UUID,
    trust_score_id: UUID,
    profile_type: CryptoProfileType,
) -> CryptoProfile:
    """Record one selection and return the row, without committing."""
    row = CryptoProfile(
        document_id=document_id,
        trust_score_id=trust_score_id,
        profile_type=profile_type,
    )
    session.add(row)
    session.flush()
    return row


def profile_selected_audit_payload(
    *,
    document_id: UUID,
    trust_score_id: UUID,
    crypto_profile_id: UUID,
    profile_type: CryptoProfileType,
    consensus_value: Decimal,
    consensus_version: str,
) -> dict[str, Any]:
    """Audit payload for one selection. JSON primitives only.

    Thresholds are the placeholder constants from :mod:`app.crypto.selector`.
    They are recorded so a stored profile remains attributable after they
    change.
    """
    return {
        "crypto_profile_id": str(crypto_profile_id),
        "document_id": str(document_id),
        "trust_score_id": str(trust_score_id),
        "profile_type": profile_type.value,
        "consensus_value": str(consensus_value),
        "consensus_version": consensus_version,
        "post_quantum_max": str(POST_QUANTUM_MAX),
        "hybrid_max": str(HYBRID_MAX),
    }
