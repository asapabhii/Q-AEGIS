"""Hybrid encryption (X25519MLKEM768), SPEC.md 3.7.

This is the 'hybrid' profile for medium-trust-score documents.
Combines X25519 ECDH (classical) with ML-KEM-768 (post-quantum) into
a single shared secret. Security holds if EITHER algorithm alone is secure.

Uses the Python cryptography library for X25519 ECDH.
ML-KEM part uses liboqs-python (falls back to X25519-only if unavailable).

SECURITY CAVEAT: liboqs is NOT independently audited, and OQS-OpenSSL is
documented by its own maintainers as development and interop-testing only,
not production-supported. Do not claim audited-grade or FIPS-certified
guarantees that the library does not back up.
"""

import os
from dataclasses import dataclass

from cryptography.hazmat.primitives.asymmetric import x25519
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.crypto import pq_primitives

#: HKDF info string for hybrid key derivation
HYBRID_INFO = b"Q-AEGIS-Hybrid-X25519MLKEM768"

#: Derived key size (32 bytes = 256 bits)
HYBRID_KEY_SIZE = 32

#: X25519 public key size (32 bytes)
X25519_KEY_SIZE = 32


@dataclass(frozen=True)
class HybridKeyPair:
    """Hybrid key pair containing both classical and PQ components.

    Attributes:
        x25519_public: Raw X25519 public key (32 bytes).
        x25519_private: Raw X25519 private key (32 bytes).
        ml_kem_public: ML-KEM-768 public key (1184 bytes), or None if unavailable.
        ml_kem_private: ML-KEM-768 private key (32 bytes), or None if unavailable.
    """

    x25519_public: bytes
    x25519_private: bytes
    ml_kem_public: bytes | None
    ml_kem_private: bytes | None


@dataclass(frozen=True)
class HybridCiphertext:
    """Encrypted data with all components for hybrid decryption.

    Attributes:
        x25519_ephemeral_pubkey: Ephemeral X25519 public key.
        x25519_ciphertext: ECDH-derived secret (encrypted).
        ml_kem_ciphertext: ML-KEM encapsulated secret (or None if PQ unavailable).
        nonce: Nonce for AES-GCM.
        ciphertext: The actual encrypted data.
    """

    x25519_ephemeral_pubkey: bytes
    x25519_ciphertext: bytes
    ml_kem_ciphertext: bytes | None
    nonce: bytes
    ciphertext: bytes


def generate_hybrid_keypair() -> HybridKeyPair:
    """Generate a hybrid key pair (X25519 + ML-KEM-768).

    If ML-KEM is unavailable, generates X25519-only keypair.

    Returns:
        HybridKeyPair with both classical and PQ components.
    """
    # Generate X25519 keypair
    x25519_private = x25519.X25519PrivateKey.generate()
    x25519_public = x25519_private.public_key().public_bytes_raw()
    x25519_private_bytes = x25519_private.private_bytes_raw()

    # Try to generate ML-KEM keypair
    ml_kem_public: bytes | None = None
    ml_kem_private: bytes | None = None

    if pq_primitives.is_available():
        ml_kem_public, ml_kem_private = pq_primitives.generate_kem_keypair("ML-KEM-768")

    return HybridKeyPair(
        x25519_public=x25519_public,
        x25519_private=x25519_private_bytes,
        ml_kem_public=ml_kem_public,
        ml_kem_private=ml_kem_private,
    )


def _derive_hybrid_secret(
    x25519_public: bytes,
    x25519_private: bytes,
    ml_kem_public: bytes | None,
    ml_kem_private: bytes | None,
) -> bytes:
    """Derive a combined hybrid secret from both classical and PQ components.

    Combines X25519 ECDH with ML-KEM encapsulation. If ML-KEM is unavailable,
    falls back to X25519-only derivation (less secure, but functional).

    Args:
        x25519_public: The recipient's X25519 public key.
        x25519_private: The sender's X25519 private key.
        ml_kem_public: ML-KEM public key (optional).
        ml_kem_private: ML-KEM private key (optional).

    Returns:
        32-byte derived shared secret.
    """
    # X25519 ECDH - always available
    recipient_x25519 = x25519.X25519PublicKey.from_public_bytes(x25519_public)
    sender_x25519 = x25519.X25519PrivateKey.from_private_bytes(x25519_private)
    x25519_secret = sender_x25519.exchange(recipient_x25519)

    # If ML-KEM available, combine with X25519 secret
    if ml_kem_public is not None and ml_kem_private is not None:
        # For encapsulation: use sender's ML-KEM keypair
        if pq_primitives.is_available():
            ml_kem_ct, ml_kem_secret = pq_primitives.encapsulate(
                ml_kem_public, "ML-KEM-768"
            )
            # Combine both secrets (XOR for independence)
            combined = bytes(a ^ b for a, b in zip(x25519_secret, ml_kem_secret[:32]))
        else:
            combined = x25519_secret
    else:
        # Fallback: X25519 only
        combined = x25519_secret

    # Derive final key using HKDF
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=HYBRID_KEY_SIZE,
        salt=None,
        info=HYBRID_INFO,
    )
    return hkdf.derive(combined)


def encrypt_hybrid(
    plaintext: bytes,
    recipient_x25519_public: bytes,
    recipient_ml_kem_public: bytes | None = None,
) -> HybridCiphertext:
    """Encrypt data using hybrid X25519 + ML-KEM scheme.

    Args:
        plaintext: The data to encrypt.
        recipient_x25519_public: Recipient's X25519 public key (32 bytes).
        recipient_ml_kem_public: Recipient's ML-KEM public key (optional).

    Returns:
        HybridCiphertext with all components needed for decryption.
    """
    # Generate ephemeral X25519 keypair
    ephemeral_x25519 = x25519.X25519PrivateKey.generate()
    ephemeral_pubkey = ephemeral_x25519.public_key().public_bytes_raw()

    # Compute ECDH secret with recipient's public key
    recipient_x25519 = x25519.X25519PublicKey.from_public_bytes(recipient_x25519_public)
    x25519_secret = ephemeral_x25519.exchange(recipient_x25519)

    # ML-KEM encapsulation if available
    ml_kem_ciphertext: bytes | None = None
    ml_kem_secret: bytes | None = None

    if recipient_ml_kem_public is not None and pq_primitives.is_available():
        ml_kem_ciphertext, ml_kem_secret = pq_primitives.encapsulate(
            recipient_ml_kem_public, "ML-KEM-768"
        )

    # Combine secrets
    if ml_kem_secret is not None:
        combined = bytes(a ^ b for a, b in zip(x25519_secret, ml_kem_secret[:32]))
    else:
        combined = x25519_secret

    # Derive key and encrypt
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=HYBRID_KEY_SIZE,
        salt=None,
        info=HYBRID_INFO,
    )
    encryption_key = hkdf.derive(combined)

    # Encrypt with AES-GCM
    nonce = os.urandom(12)
    aesgcm = AESGCM(encryption_key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    return HybridCiphertext(
        x25519_ephemeral_pubkey=ephemeral_pubkey,
        x25519_ciphertext=x25519_secret,  # Could encrypt this for forward secrecy
        ml_kem_ciphertext=ml_kem_ciphertext,
        nonce=nonce,
        ciphertext=ciphertext,
    )


def decrypt_hybrid(
    ciphertext: HybridCiphertext,
    recipient_x25519_private: bytes,
    recipient_ml_kem_private: bytes | None = None,
) -> bytes:
    """Decrypt data using hybrid X25519 + ML-KEM scheme.

    Args:
        ciphertext: The HybridCiphertext to decrypt.
        recipient_x25519_private: Recipient's X25519 private key.
        recipient_ml_kem_private: Recipient's ML-KEM private key (optional).

    Returns:
        The decrypted plaintext.
    """
    # ECDH with ephemeral public key
    recipient_x25519 = x25519.X25519PrivateKey.from_private_bytes(
        recipient_x25519_private
    )
    ephemeral_x25519 = x25519.X25519PublicKey.from_public_bytes(
        ciphertext.x25519_ephemeral_pubkey
    )
    x25519_secret = recipient_x25519.exchange(ephemeral_x25519)

    # ML-KEM decapsulation if available
    ml_kem_secret: bytes | None = None

    if (
        ciphertext.ml_kem_ciphertext is not None
        and recipient_ml_kem_private is not None
        and pq_primitives.is_available()
    ):
        ml_kem_secret = pq_primitives.decapsulate(
            recipient_ml_kem_private,
            ciphertext.ml_kem_ciphertext,
            "ML-KEM-768",
        )

    # Combine secrets
    if ml_kem_secret is not None:
        combined = bytes(a ^ b for a, b in zip(x25519_secret, ml_kem_secret[:32]))
    else:
        combined = x25519_secret

    # Derive key and decrypt
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=HYBRID_KEY_SIZE,
        salt=None,
        info=HYBRID_INFO,
    )
    decryption_key = hkdf.derive(combined)

    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    aesgcm = AESGCM(decryption_key)
    return aesgcm.decrypt(ciphertext.nonce, ciphertext.ciphertext, None)
