"""Versioned AI recommendation from a trust consensus, ``SPEC.md`` 3.5 → 3.6.

Until LangGraph agents existed, ``ai_recommendation`` on
``POST /policy-decisions`` was caller-asserted. With FR-3 producing real
scores, the assessment pipeline derives the recommendation from
``consensus_value`` so the gate is not fed an arbitrary client string.

Thresholds use the policy-calibrated bands logged in ``docs/decisions.md`` on
2026-09-15. Ambiguity resolves toward more protection (lower trust → stronger
action). Changing any cut-point requires bumping ``RECOMMENDATION_VERSION``.
"""

from decimal import Decimal

from app.db.enums import PolicyAction

#: Recorded on assessment audit payloads so historical decisions stay attributable.
RECOMMENDATION_VERSION = "trust-recommendation-policy-bands-1.0.0"

#: Inclusive upper bound of the deny band. At the boundary, deny wins.
DENY_MAX = Decimal("0.250")

#: Inclusive upper bound of force_pqc. Above this and at/under MFA_MAX → MFA.
FORCE_PQC_MAX = Decimal("0.500")

#: Inclusive upper bound of require_mfa. Above this → allow.
REQUIRE_MFA_MAX = Decimal("0.750")


def recommend_from_consensus(consensus_value: Decimal) -> PolicyAction:
    """Map a trust consensus in ``[0, 1]`` to a :class:`PolicyAction`.

    Boundaries resolve toward more protection: ``0.250`` is deny, not
    ``force_pqc``; ``0.750`` is ``require_mfa``, not ``allow``.

    Args:
        consensus_value: Stored ``trust_scores.consensus_value``.

    Returns:
        The action the AI layer would propose before the policy gate.

    Raises:
        ValueError: if the value is outside ``[0, 1]``.
    """
    if consensus_value < Decimal("0") or consensus_value > Decimal("1"):
        raise ValueError(f"consensus_value must be in [0, 1], got {consensus_value!r}")
    if consensus_value <= DENY_MAX:
        return PolicyAction.DENY
    if consensus_value <= FORCE_PQC_MAX:
        return PolicyAction.FORCE_PQC
    if consensus_value <= REQUIRE_MFA_MAX:
        return PolicyAction.REQUIRE_MFA
    return PolicyAction.ALLOW
