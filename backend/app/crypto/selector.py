"""Calibrated crypto selector, ``SPEC.md`` 3.7, ``PRD.md`` FR-6.

Maps a numeric trust score onto one of the three protection profiles using the
policy-calibrated bands logged in ``docs/decisions.md`` on 2026-09-15.
Persist, ``trust_score_id``, and the audit entry live on
``POST /api/v1/crypto-profiles``.

SECURITY CAVEAT: liboqs is NOT independently audited, and OQS-OpenSSL is
documented by its own maintainers as development and interop-testing only, not
production-supported. Do not claim audited-grade or FIPS-certified guarantees
that the library does not back up.

Key management this phase is environment-configured secrets, not a hardware
security module (``PRD.md`` NG5).
"""

import math

from app.db.enums import CryptoProfileType

#: Recorded in tests/docs so historical selections stay attributable.
SELECTOR_VERSION = "trust-crypto-policy-bands-1.0.0"

#: Inclusive upper bound of the full post-quantum band. At the boundary the
#: selector picks the stronger profile, matching ``AGENTS.md``: ambiguity
#: resolves toward more protection, never less.
POST_QUANTUM_MAX = 0.50

#: Inclusive upper bound of the hybrid band. Above this, AES-256-GCM.
HYBRID_MAX = 0.85


def select_crypto_profile(trust_score: float) -> CryptoProfileType:
    """Map a trust score in ``[0.0, 1.0]`` to a protection profile.

    Boundary values resolve toward more protection: ``0.50`` is
    post-quantum, not hybrid; ``0.85`` is hybrid, not AES-256. Persist is
    ``POST /api/v1/crypto-profiles``, not this function.

    Invalid input is refused, not coerced. ``NaN`` and infinities make every
    ``<=`` comparison false in IEEE-754, which would otherwise fall through to
    AES-256 — the weakest profile. That is the opposite of fail-closed, so
    non-finite and out-of-range scores raise ``ValueError``.

    SECURITY CAVEAT: liboqs is NOT independently audited, and OQS-OpenSSL is
    documented by its own maintainers as development and interop-testing only,
    not production-supported. Do not claim audited-grade or FIPS-certified
    guarantees that the library does not back up.

    Args:
        trust_score: Consensus trust score. Must be finite and in ``[0.0, 1.0]``.

    Returns:
        A :class:`~app.db.enums.CryptoProfileType` member, never a raw string.

    Raises:
        ValueError: if ``trust_score`` is non-finite or outside ``[0.0, 1.0]``.
    """
    if not isinstance(trust_score, (int, float)) or isinstance(trust_score, bool):
        raise ValueError(
            f"trust_score must be a real number in [0.0, 1.0], got {trust_score!r}."
        )
    if not math.isfinite(trust_score) or trust_score < 0.0 or trust_score > 1.0:
        raise ValueError(
            f"trust_score must be finite and in [0.0, 1.0], got {trust_score!r}."
        )

    if trust_score <= POST_QUANTUM_MAX:
        return CryptoProfileType.POST_QUANTUM
    if trust_score <= HYBRID_MAX:
        return CryptoProfileType.HYBRID
    return CryptoProfileType.AES256
