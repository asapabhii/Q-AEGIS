"""Tests for the crypto-selector stub.

This tests a stub implementation.

SECURITY CAVEAT: liboqs is NOT independently audited, and OQS-OpenSSL is
documented by its own maintainers as development and interop-testing only, not
production-supported. Do not claim audited-grade or FIPS-certified guarantees
that the library does not back up.
"""

import math

import pytest

from app.crypto import selector
from app.crypto.selector import select_crypto_profile
from app.db.enums import CryptoProfileType


def test_crypto_selector_is_stub() -> None:
    """The module and function are explicitly labeled as a stub."""
    assert selector.__doc__ is not None
    assert "stub" in selector.__doc__.lower()
    assert select_crypto_profile.__doc__ is not None
    assert "stub" in select_crypto_profile.__doc__.lower()


def test_select_crypto_profile_returns_the_enum() -> None:
    """Callers get CryptoProfileType, not a raw string they could misspell."""
    result = select_crypto_profile(0.5)
    assert result is CryptoProfileType.HYBRID
    assert result.value == "hybrid"


def test_select_crypto_profile_boundaries() -> None:
    """Every published boundary resolves toward more protection."""
    assert select_crypto_profile(0.0) is CryptoProfileType.POST_QUANTUM
    assert select_crypto_profile(0.39) is CryptoProfileType.POST_QUANTUM
    assert select_crypto_profile(0.4) is CryptoProfileType.POST_QUANTUM
    assert select_crypto_profile(0.41) is CryptoProfileType.HYBRID

    assert select_crypto_profile(0.79) is CryptoProfileType.HYBRID
    assert select_crypto_profile(0.8) is CryptoProfileType.HYBRID
    assert select_crypto_profile(0.81) is CryptoProfileType.AES256
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
