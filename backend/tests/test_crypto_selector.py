"""Tests for the calibrated crypto selector.

SECURITY CAVEAT: liboqs is NOT independently audited, and OQS-OpenSSL is
documented by its own maintainers as development and interop-testing only, not
production-supported. Do not claim audited-grade or FIPS-certified guarantees
that the library does not back up.
"""

import math

import pytest

from app.crypto import selector
from app.crypto.selector import SELECTOR_VERSION, select_crypto_profile
from app.db.enums import CryptoProfileType


def test_crypto_selector_is_not_labeled_as_stub() -> None:
    """The threshold selector has a documented policy-band calibration."""
    assert selector.__doc__ is not None
    assert "stub" not in selector.__doc__.lower()
    assert "policy-calibrated" in selector.__doc__.lower()
    assert select_crypto_profile.__doc__ is not None
    assert "stub" not in select_crypto_profile.__doc__.lower()
    assert SELECTOR_VERSION == "trust-crypto-policy-bands-1.0.0"


def test_select_crypto_profile_returns_the_enum() -> None:
    """Callers get CryptoProfileType, not a raw string they could misspell."""
    result = select_crypto_profile(0.51)
    assert result is CryptoProfileType.HYBRID
    assert result.value == "hybrid"


def test_select_crypto_profile_boundaries() -> None:
    """Every published boundary resolves toward more protection."""
    assert select_crypto_profile(0.0) is CryptoProfileType.POST_QUANTUM
    assert select_crypto_profile(0.49) is CryptoProfileType.POST_QUANTUM
    assert select_crypto_profile(0.5) is CryptoProfileType.POST_QUANTUM
    assert select_crypto_profile(0.51) is CryptoProfileType.HYBRID

    assert select_crypto_profile(0.84) is CryptoProfileType.HYBRID
    assert select_crypto_profile(0.85) is CryptoProfileType.HYBRID
    assert select_crypto_profile(0.86) is CryptoProfileType.AES256
    assert select_crypto_profile(1.0) is CryptoProfileType.AES256


@pytest.mark.parametrize(
    "bad",
    [
        float("nan"),
        float("inf"),
        float("-inf"),
        -0.01,
        1.01,
        True,
        "0.5",
    ],
)
def test_select_crypto_profile_refuses_invalid_scores(bad: object) -> None:
    """Garbage input is refused, not mapped to AES-256.

    NaN in particular would otherwise fall through every ``<=`` check and
    return the weakest profile, which is the failure this test exists to
    prevent.
    """
    with pytest.raises(ValueError):
        select_crypto_profile(bad)  # type: ignore[arg-type]


def test_nan_does_not_resolve_to_aes256() -> None:
    """Explicit pin on the IEEE-754 trap the original stub had."""
    with pytest.raises(ValueError):
        select_crypto_profile(math.nan)
