"""Tests for byte-level encryption, ``SPEC.md`` 3.7.

SECURITY CAVEAT: liboqs is NOT independently audited, and OQS-OpenSSL is
documented by its own maintainers as development and interop-testing only, not
production-supported. Do not claim audited-grade or FIPS-certified guarantees
that the library does not back up.
"""

from __future__ import annotations

import base64
import os
from unittest.mock import patch

import pytest

from app.crypto.engine import (
    ALGORITHM_AES256,
    decrypt_document_bytes,
    encrypt_document_bytes,
)
from app.crypto.exceptions import LiboqsUnavailableError
from app.crypto.key_management import unwrap_dek, wrap_dek
from app.crypto.oqs_support import oqs_available
from app.db.enums import CryptoProfileType

TEST_MASTER_KEY = base64.urlsafe_b64encode(os.urandom(32)).decode("ascii")


@pytest.fixture
def master_key(monkeypatch: pytest.MonkeyPatch) -> bytes:
    """Configure a valid master key for encryption tests."""
    monkeypatch.setenv("CRYPTO_MASTER_KEY", TEST_MASTER_KEY)
    return base64.urlsafe_b64decode(TEST_MASTER_KEY + "=" * (-len(TEST_MASTER_KEY) % 4))


def test_wrap_and_unwrap_dek_roundtrip(master_key: bytes) -> None:
    """Master-key wrapping round-trips arbitrary DEK payloads."""
    payload = b"\x01" + os.urandom(32)
    wrapped = wrap_dek(payload, master_key=master_key)
    assert unwrap_dek(wrapped, master_key=master_key) == payload


def test_aes256_encrypt_decrypt_roundtrip(master_key: bytes) -> None:
    """AES-256-GCM profile encrypts and decrypts document bytes."""
    plaintext = b"restricted quarterly forecast"
    result = encrypt_document_bytes(
        plaintext,
        CryptoProfileType.AES256,
        master_key=master_key,
    )
    assert result.algorithm == ALGORITHM_AES256
    assert result.kem_ciphertext is None
    assert result.ciphertext != plaintext
    recovered = decrypt_document_bytes(
        result,
        CryptoProfileType.AES256,
        master_key=master_key,
    )
    assert recovered == plaintext


@pytest.mark.parametrize(
    "profile",
    [CryptoProfileType.HYBRID, CryptoProfileType.POST_QUANTUM],
)
def test_pq_profiles_fail_closed_without_oqs(
    master_key: bytes, profile: CryptoProfileType
) -> None:
    """Hybrid and post-quantum never fall back to AES when liboqs is missing."""
    with patch("app.crypto.oqs_support.oqs_available", return_value=False):
        with pytest.raises(LiboqsUnavailableError):
            encrypt_document_bytes(b"secret", profile, master_key=master_key)


def test_hybrid_encrypt_decrypt_roundtrip(master_key: bytes) -> None:
    """Hybrid profile round-trips when liboqs is available."""
    if not oqs_available():
        pytest.skip("liboqs-python is not installed")
    plaintext = b"harvest-now-decrypt-later payload"
    result = encrypt_document_bytes(
        plaintext,
        CryptoProfileType.HYBRID,
        master_key=master_key,
    )
    assert result.kem_ciphertext is not None
    recovered = decrypt_document_bytes(
        result,
        CryptoProfileType.HYBRID,
        master_key=master_key,
    )
    assert recovered == plaintext


def test_post_quantum_encrypt_decrypt_roundtrip(master_key: bytes) -> None:
    """Post-quantum profile round-trips when liboqs is available."""
    if not oqs_available():
        pytest.skip("liboqs-python is not installed")
    plaintext = b"level-5 protection payload"
    result = encrypt_document_bytes(
        plaintext,
        CryptoProfileType.POST_QUANTUM,
        master_key=master_key,
    )
    assert result.kem_ciphertext is not None
    recovered = decrypt_document_bytes(
        result,
        CryptoProfileType.POST_QUANTUM,
        master_key=master_key,
    )
    assert recovered == plaintext
