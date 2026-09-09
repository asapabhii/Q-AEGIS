"""AES-256-GCM encryption for the Crypto Engine, `SPEC.md` 3.7.

This is the 'aes256' profile for high-trust-score documents.
Uses the Python cryptography library (already in requirements).

SECURITY CAVEAT: liboqs is NOT independently audited, and OQS-OpenSSL is
documented by its own maintainers as development and interop-testing only,
not production-supported. Do not claim audited-grade or FIPS-certified
guarantees that the library does not back up.
"""

import os
from dataclasses import dataclass
from typing import Any

from cryptography.hazmat.primitives.ciphers.aead import AESGCM

#: AES-256 key size in bytes (32 bytes = 256 bits)
AES_256_KEY_SIZE = 32

#: GCM nonce size in bytes (96 bits = 12 bytes, recommended by NIST)
GCM_NONCE_SIZE = 12

#: GCM tag size in bytes (128 bits = 16 bytes)
GCM_TAG_SIZE = 16


@dataclass(frozen=True)
class AESCiphertext:
    """Encrypted data with nonce and authentication tag.

    Attributes:
        ciphertext: The encrypted data (includes tag appended).
        nonce: The nonce used for encryption.
    """

    ciphertext: bytes
    nonce: bytes


def generate_aes_key() -> bytes:
    """Generate a random 256-bit AES key.

    Uses os.urandom for cryptographically secure random bytes.

    Returns:
        32-byte AES-256 key.

    Raises:
        OSError: If the system entropy source is unavailable.
    """
    return os.urandom(AES_256_KEY_SIZE)


def encrypt_aes_gcm(plaintext: bytes, key: bytes) -> AESCiphertext:
    """Encrypt plaintext using AES-256-GCM.

    AES-GCM provides both confidentiality (encryption) and authenticity
    (authentication tag). The tag is appended to the ciphertext.

    Args:
        plaintext: The data to encrypt.
        key: 32-byte AES-256 key.

    Returns:
        AESCiphertext with ciphertext (including tag) and nonce.

    Raises:
        ValueError: If key is not 32 bytes.
    """
    if len(key) != AES_256_KEY_SIZE:
        raise ValueError(
            "AES-256 key must be {} bytes, got {}".format(AES_256_KEY_SIZE, len(key))
        )

    # Generate random nonce
    nonce = os.urandom(GCM_NONCE_SIZE)

    # Create AES-GCM cipher
    aesgcm = AESGCM(key)

    # Encrypt (tag is appended to ciphertext automatically)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    return AESCiphertext(ciphertext=ciphertext, nonce=nonce)


def decrypt_aes_gcm(ciphertext: bytes, key: bytes, nonce: bytes) -> bytes:
    """Decrypt AES-256-GCM encrypted data.

    Verifies authentication tag before returning plaintext. If the tag
    is invalid (data has been tampered with), raises an exception.

    Args:
        ciphertext: The encrypted data (including authentication tag).
        key: 32-byte AES-256 key.
        nonce: The nonce used during encryption.

    Returns:
        The decrypted plaintext.

    Raises:
        ValueError: If key is not 32 bytes or nonce is not 12 bytes.
        cryptography.exceptions.InvalidTag: If authentication fails
            (data has been tampered with).
    """
    if len(key) != AES_256_KEY_SIZE:
        raise ValueError(
            "AES-256 key must be {} bytes, got {}".format(AES_256_KEY_SIZE, len(key))
        )

    if len(nonce) != GCM_NONCE_SIZE:
        raise ValueError(
            "GCM nonce must be {} bytes, got {}".format(GCM_NONCE_SIZE, len(nonce))
        )

    aesgcm = AESGCM(key)
    return aesgcm.decrypt(nonce, ciphertext, None)


def encrypt_with_metadata(plaintext: bytes, key: bytes) -> dict[str, Any]:
    """Encrypt with full metadata for storage.

    Creates a dictionary suitable for storing in crypto_profiles table.

    Args:
        plaintext: The data to encrypt.
        key: 32-byte AES-256 key.

    Returns:
        Dictionary with:
        - ciphertext: Base64-encoded ciphertext
        - nonce: Base64-encoded nonce
        - key_id: Reference to the key (for future key rotation)
    """
    import base64

    result = encrypt_aes_gcm(plaintext, key)

    return {
        "ciphertext": base64.b64encode(result.ciphertext).decode("ascii"),
        "nonce": base64.b64encode(result.nonce).decode("ascii"),
        "algorithm": "AES-256-GCM",
        "key_size": AES_256_KEY_SIZE * 8,  # bits
    }


def decrypt_with_metadata(encrypted_data: dict[str, Any], key: bytes) -> bytes:
    """Decrypt data that was encrypted with metadata.

    Args:
        encrypted_data: Dictionary with ciphertext and nonce (base64 encoded).
        key: 32-byte AES-256 key.

    Returns:
        The decrypted plaintext.
    """
    import base64

    ciphertext = base64.b64decode(encrypted_data["ciphertext"])
    nonce = base64.b64decode(encrypted_data["nonce"])

    return decrypt_aes_gcm(ciphertext, key, nonce)
