"""Master-key DEK wrapping for shredding, ``SPEC.md`` 3.7 / ``PRD.md`` NG5.

The master secret is environment-configured, not hardware-backed. Destroying
``wrapped_dek`` (or the master key) makes stored ciphertext unreadable without
deleting audit rows.

SECURITY CAVEAT: liboqs is NOT independently audited, and OQS-OpenSSL is
documented by its own maintainers as development and interop-testing only, not
production-supported. Do not claim audited-grade or FIPS-certified guarantees
that the library does not back up.
"""

from __future__ import annotations

import base64
import os

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM

from app.config import get_settings
from app.crypto.exceptions import CryptoConfigurationError, CryptoDecryptError

DEK_SIZE = 32
MASTER_KEY_SIZE = 32
WRAP_NONCE_SIZE = 12

WRAP_VERSION_AES256 = 1
WRAP_VERSION_HYBRID = 2
WRAP_VERSION_POST_QUANTUM = 3


def decode_master_key(raw: str) -> bytes:
    """Decode a base64url ``CRYPTO_MASTER_KEY`` value to 32 bytes.

    SECURITY CAVEAT: liboqs is NOT independently audited. This key wraps DEKs
    for all profiles, including those that use liboqs.

    Args:
        raw: Base64url-encoded master key from the environment.

    Returns:
        The decoded 32-byte master key.

    Raises:
        CryptoConfigurationError: if decoding fails or the key length is wrong.
    """
    padded = raw + "=" * (-len(raw) % 4)
    try:
        key = base64.urlsafe_b64decode(padded.encode("ascii"))
    except ValueError as exc:
        raise CryptoConfigurationError(
            "CRYPTO_MASTER_KEY must be valid base64url."
        ) from exc
    if len(key) != MASTER_KEY_SIZE:
        raise CryptoConfigurationError(
            f"CRYPTO_MASTER_KEY must decode to {MASTER_KEY_SIZE} bytes, got {len(key)}."
        )
    return key


def get_master_key() -> bytes:
    """Load and validate the configured master key.

    SECURITY CAVEAT: liboqs is NOT independently audited.

    Raises:
        CryptoConfigurationError: when ``CRYPTO_MASTER_KEY`` is unset or invalid.
    """
    raw = get_settings().crypto_master_key
    if raw is None or not raw.strip():
        raise CryptoConfigurationError("CRYPTO_MASTER_KEY is not configured.")
    return decode_master_key(raw.strip())


def wrap_dek(payload: bytes, master_key: bytes | None = None) -> bytes:
    """Encrypt a DEK or profile-specific secret payload under the master key.

    SECURITY CAVEAT: liboqs is NOT independently audited.

    The returned blob is ``nonce || ciphertext || tag`` suitable for storage in
    ``document_ciphertexts.wrapped_dek``.

    Args:
        payload: Plain secret bytes to protect (version byte plus key material).
        master_key: Optional override for tests; defaults to ``CRYPTO_MASTER_KEY``.

    Returns:
        Master-key-wrapped bytes.

    Raises:
        CryptoConfigurationError: when no usable master key is available.
    """
    key = master_key if master_key is not None else get_master_key()
    nonce = os.urandom(WRAP_NONCE_SIZE)
    ciphertext = AESGCM(key).encrypt(nonce, payload, None)
    return nonce + ciphertext


def unwrap_dek(wrapped: bytes, master_key: bytes | None = None) -> bytes:
    """Decrypt a master-key-wrapped DEK or secret payload.

    SECURITY CAVEAT: liboqs is NOT independently audited.

    Args:
        wrapped: ``nonce || ciphertext || tag`` produced by :func:`wrap_dek`.
        master_key: Optional override for tests; defaults to ``CRYPTO_MASTER_KEY``.

    Returns:
        The original payload bytes.

    Raises:
        CryptoConfigurationError: when no usable master key is available.
        CryptoDecryptError: when authentication fails.
    """
    if len(wrapped) < WRAP_NONCE_SIZE + 16:
        raise CryptoDecryptError("wrapped_dek is too short to contain nonce and tag.")
    key = master_key if master_key is not None else get_master_key()
    nonce = wrapped[:WRAP_NONCE_SIZE]
    ciphertext = wrapped[WRAP_NONCE_SIZE:]
    try:
        return AESGCM(key).decrypt(nonce, ciphertext, None)
    except InvalidTag as exc:
        raise CryptoDecryptError("Wrapped key authentication failed.") from exc
