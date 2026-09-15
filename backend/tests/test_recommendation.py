"""Tests for consensus → policy recommendation mapping."""

from decimal import Decimal

import pytest

from app.db.enums import PolicyAction
from app.trust_engine.recommendation import (
    RECOMMENDATION_VERSION,
    recommend_from_consensus,
)


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("0.000", PolicyAction.DENY),
        ("0.250", PolicyAction.DENY),
        ("0.251", PolicyAction.FORCE_PQC),
        ("0.500", PolicyAction.FORCE_PQC),
        ("0.501", PolicyAction.REQUIRE_MFA),
        ("0.750", PolicyAction.REQUIRE_MFA),
        ("0.751", PolicyAction.ALLOW),
        ("1.000", PolicyAction.ALLOW),
    ],
)
def test_recommend_from_consensus_bands(value: str, expected: PolicyAction) -> None:
    assert recommend_from_consensus(Decimal(value)) is expected


def test_recommend_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        recommend_from_consensus(Decimal("1.001"))


def test_recommendation_version_records_policy_band_calibration() -> None:
    assert RECOMMENDATION_VERSION == "trust-recommendation-policy-bands-1.0.0"
