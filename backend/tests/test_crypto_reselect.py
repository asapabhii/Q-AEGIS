"""Asynchronous crypto reselection on trust change, ``PRD.md`` FR-6.

Covers :func:`app.crypto.reselect.reselect_for_trust_score`: a trust score written
outside the synchronous pipeline (``POST /trust-scores``) drives a new
``crypto_profiles`` row when the protection band changes, and is a no-op when a
profile already exists for that trust score or the band is unchanged.
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.crypto.reselect import reselect_for_trust_score
from app.db.enums import AuditEventType, CryptoProfileType, UserRole
from app.db.models import Document, User
from app.db.repositories import crypto as crypto_repo
from tests import factories


def _document(session: Session, users: dict[UserRole, User]) -> Document:
    from app.db.repositories import documents as documents_repo

    return documents_repo.register_document(
        session,
        uploaded_by=users[UserRole.DATA_OWNER].id,
        filename="reselect-target.pdf",
    )


def _crypto_audit_count(session: Session, document_id) -> int:
    return session.execute(
        text(
            "SELECT count(*) FROM audit_log "
            "WHERE document_id = :doc AND event_type = :evt"
        ),
        {"doc": str(document_id), "evt": AuditEventType.CRYPTO_PROFILE_SELECTED.value},
    ).scalar_one()


def test_band_change_appends_new_profile_and_audit(
    db_session: Session, seeded_users: dict[UserRole, User]
) -> None:
    document = _document(db_session, seeded_users)

    # Prior protection: AES-256 from an earlier high-trust score.
    high_risk = factories.make_risk_score(db_session, document)
    high_trust = factories.make_trust_score(
        db_session, document, high_risk, consensus_value="0.900"
    )
    factories.make_crypto_profile(
        db_session, document, high_trust, profile_type=CryptoProfileType.AES256
    )
    before = _crypto_audit_count(db_session, document.id)

    # A new low-trust score with no profile bound to it yet.
    low_risk = factories.make_risk_score(db_session, document)
    low_trust = factories.make_trust_score(
        db_session, document, low_risk, consensus_value="0.300"
    )

    profile = reselect_for_trust_score(db_session, trust_score_id=low_trust.id)

    assert profile is not None
    assert profile.profile_type is CryptoProfileType.POST_QUANTUM
    assert profile.trust_score_id == low_trust.id
    # A protection profile is now bound to the low-trust score.
    assert crypto_repo.exists_for_trust_score(db_session, low_trust.id)
    # Exactly one new crypto-selection audit entry was written.
    assert _crypto_audit_count(db_session, document.id) == before + 1


def test_idempotent_when_profile_already_bound(
    db_session: Session, seeded_users: dict[UserRole, User]
) -> None:
    document = _document(db_session, seeded_users)
    risk = factories.make_risk_score(db_session, document)
    trust = factories.make_trust_score(
        db_session, document, risk, consensus_value="0.300"
    )
    # The synchronous pipeline already produced a profile for this trust score.
    factories.make_crypto_profile(
        db_session, document, trust, profile_type=CryptoProfileType.POST_QUANTUM
    )
    before = _crypto_audit_count(db_session, document.id)

    result = reselect_for_trust_score(db_session, trust_score_id=trust.id)

    assert result is None
    assert _crypto_audit_count(db_session, document.id) == before


def test_no_append_when_band_unchanged(
    db_session: Session, seeded_users: dict[UserRole, User]
) -> None:
    document = _document(db_session, seeded_users)
    # Current protection is HYBRID from a mid-trust score.
    first_risk = factories.make_risk_score(db_session, document)
    first_trust = factories.make_trust_score(
        db_session, document, first_risk, consensus_value="0.650"
    )
    factories.make_crypto_profile(
        db_session, document, first_trust, profile_type=CryptoProfileType.HYBRID
    )
    before = _crypto_audit_count(db_session, document.id)

    # A new trust score in the same (HYBRID) band, no profile bound.
    second_risk = factories.make_risk_score(db_session, document)
    second_trust = factories.make_trust_score(
        db_session, document, second_risk, consensus_value="0.700"
    )

    result = reselect_for_trust_score(db_session, trust_score_id=second_trust.id)

    assert result is None
    assert _crypto_audit_count(db_session, document.id) == before


def test_first_ever_profile_is_appended(
    db_session: Session, seeded_users: dict[UserRole, User]
) -> None:
    document = _document(db_session, seeded_users)
    risk = factories.make_risk_score(db_session, document)
    trust = factories.make_trust_score(
        db_session, document, risk, consensus_value="0.400"
    )

    profile = reselect_for_trust_score(db_session, trust_score_id=trust.id)

    assert profile is not None
    assert profile.profile_type is CryptoProfileType.POST_QUANTUM


def test_unknown_trust_score_is_noop(
    db_session: Session, seeded_users: dict[UserRole, User]
) -> None:
    assert reselect_for_trust_score(db_session, trust_score_id=uuid4()) is None
