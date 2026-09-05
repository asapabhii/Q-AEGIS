"""Tests for the crypto-selector stub.

This tests a stub implementation.

SECURITY CAVEAT: liboqs is NOT independently audited, and OQS-OpenSSL is 
documented by its own maintainers as development and interop-testing only, 
not production-supported. Do not claim audited-grade or FIPS-certified 
guarantees that the library does not back up.
"""
from app.crypto.selector import select_crypto_profile
from app.crypto import selector

def test_crypto_selector_is_stub():
    """Assert that the module and function are explicitly labeled as a stub."""
    assert "stub" in selector.__doc__.lower()
    assert "stub" in select_crypto_profile.__doc__.lower()

def test_select_crypto_profile_boundaries():
    """Test every boundary of the score-to-profile mapping.
    
    Boundary cases resolve toward MORE protection.
    """
    # Threshold 1: 0.4 (post_quantum vs hybrid)
    assert select_crypto_profile(0.0) == "post_quantum"
    assert select_crypto_profile(0.39) == "post_quantum"
    assert select_crypto_profile(0.4) == "post_quantum"  # boundary resolves to more protection
    assert select_crypto_profile(0.41) == "hybrid"

    # Threshold 2: 0.8 (hybrid vs aes256)
    assert select_crypto_profile(0.79) == "hybrid"
    assert select_crypto_profile(0.8) == "hybrid"  # boundary resolves to more protection
    assert select_crypto_profile(0.81) == "aes256"
    assert select_crypto_profile(1.0) == "aes256"
