"""Tests for consensus → policy recommendation mapping."""

from decimal import Decimal

import pytest

from app.db.enums import PolicyAction
from app.trust_engine.recommendation import recommend_from_consensus


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("0.000", PolicyAction.DENY),
        ("0.300", PolicyAction.DENY),
        ("0.301", PolicyAction.FORCE_PQC),
        ("0.500", PolicyAction.FORCE_PQC),
        ("0.501", PolicyAction.REQUIRE_MFA),
        ("0.800", PolicyAction.REQUIRE_MFA),
        ("0.801", PolicyAction.ALLOW),
        ("1.000", PolicyAction.ALLOW),
    ],
)
def test_recommend_from_consensus_bands(value: str, expected: PolicyAction) -> None:
    assert recommend_from_consensus(Decimal(value)) is expected


def test_recommend_rejects_out_of_range() -> None:
    with pytest.raises(ValueError):
        recommend_from_consensus(Decimal("1.001"))
