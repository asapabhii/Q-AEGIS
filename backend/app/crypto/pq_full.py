"""Full post-quantum encryption (ML-KEM-1024 + ML-DSA-87), SPEC.md 3.7.

This is the 'post_quantum' profile for low-trust-score documents.
Uses ML-KEM-1024 (NIST level 5) for key encapsulation and ML-DSA-87
for signatures. No classical algorithms, pure post-quantum protection.

SECURITY CAVEAT: liboqs is NOT independently audited, and OQS-OpenSSL is
documented by its own maintainers as development and interop-testing only,
not production-supported. Do not claim audited-grade or FIPS-certified
guarantees that the library does not back up.
"""

import os
from dataclasses import dataclass

from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.crypto import pq_primitives

#: HKDF info string for post-quantum key derivation
PQ_INFO = b"Q-AEGIS-PQ-MLKEM1024-MLDSA87"

#: Derived key size (32 bytes = 256 bits)
PQ_KEY_SIZE = 32


@dataclass(frozen=True)
class PQKeyPair:
    """Post-quantum key pair with KEM and signature keys.

    Attributes:
        kem_public: ML-KEM-1024 public key.
        kem_private: ML-KEM-1024 private key.
        sig_public: ML-DSA-87 public key.
        sig_private: ML-DSA-87 private key.
    """

    kem_public: bytes
    kem_private: bytes
    sig_public: bytes
    sig_private: bytes


@dataclass(frozen=True)
class PQCiphertext:
    """Encrypted data with post-quantum protection.

    Attributes:
        kem_ciphertext: ML-KEM-1024 encapsulated secret.
        nonce: Nonce for AES-GCM.
        ciphertext: The encrypted data.
        signature: ML-DSA-87 signature over (nonce || ciphertext).
    """

    kem_ciphertext: bytes
    nonce: bytes
    ciphertext: bytes
    signature: bytes


def generate_pq_keypair() -> PQKeyPair:
    """Generate a full post-quantum key pair.

    Returns:
        PQKeyPair with ML-KEM-1024 and ML-DSA-87 keys.

    Raises:
        RuntimeError: If liboqs is not available.
    """
    if not pq_primitives.is_available():
        raise RuntimeError(
            "liboqs is not available. Full post-quantum encryption requires liboqs."
        )

    # Generate ML-KEM-1024 keypair for encryption
    kem_public, kem_private = pq_primitives.generate_kem_keypair(pq_primitives.PQ_KEM)

    # Generate ML-DSA-87 keypair for signing
    sig_public, sig_private = pq_primitives.generate_sig_keypair(pq_primitives.PQ_SIG)

    return PQKeyPair(
        kem_public=kem_public,
        kem_private=kem_private,
        sig_public=sig_public,
        sig_private=sig_private,
    )


def encrypt_pq(
    plaintext: bytes,
    recipient_kem_public: bytes,
    sender_sig_private: bytes,
) -> PQCiphertext:
    """Encrypt data using full post-quantum cryptography.

    Uses ML-KEM-1024 for key encapsulation and ML-DSA-87 to sign
    the ciphertext, providing both confidentiality and authenticity.

    Args:
        plaintext: The data to encrypt.
        recipient_kem_public: Recipient's ML-KEM-1024 public key.
        sender_sig_private: Sender's ML-DSA-87 private key.

    Returns:
        PQCiphertext with all components.

    Raises:
        RuntimeError: If liboqs is not available.
    """
    if not pq_primitives.is_available():
        raise RuntimeError("liboqs is not available.")

    # Encapsulate a shared secret using ML-KEM-1024
    kem_ciphertext, shared_secret = pq_primitives.encapsulate(
        recipient_kem_public, pq_primitives.PQ_KEM
    )

    # Derive encryption key from shared secret
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=PQ_KEY_SIZE,
        salt=None,
        info=PQ_INFO,
    )
    encryption_key = hkdf.derive(shared_secret)

    # Encrypt with AES-GCM
    nonce = os.urandom(12)
    aesgcm = AESGCM(encryption_key)
    ciphertext = aesgcm.encrypt(nonce, plaintext, None)

    # Sign (nonce || ciphertext) with ML-DSA-87
    to_sign = nonce + ciphertext
    signature = pq_primitives.sign(to_sign, sender_sig_private, pq_primitives.PQ_SIG)

    return PQCiphertext(
        kem_ciphertext=kem_ciphertext,
        nonce=nonce,
        ciphertext=ciphertext,
        signature=signature,
    )


def decrypt_pq(
    ciphertext: PQCiphertext,
    recipient_kem_private: bytes,
    sender_sig_public: bytes,
) -> bytes:
    """Decrypt data using full post-quantum cryptography.

    Verifies the ML-DSA-87 signature before decrypting with ML-KEM-1024.

    Args:
        ciphertext: The PQCiphertext to decrypt.
        recipient_kem_private: Recipient's ML-KEM-1024 private key.
        sender_sig_public: Sender's ML-DSA-87 public key.

    Returns:
        The decrypted plaintext.

    Raises:
        RuntimeError: If liboqs is not available.
        ValueError: If signature verification fails.
    """
    if not pq_primitives.is_available():
        raise RuntimeError("liboqs is not available.")

    # Verify signature first
    to_verify = ciphertext.nonce + ciphertext.ciphertext
    valid = pq_primitives.verify(
        to_verify,
        ciphertext.signature,
        sender_sig_public,
        pq_primitives.PQ_SIG,
    )

    if not valid:
        raise ValueError("PQ signature verification failed")

    # Decapsulate shared secret
    shared_secret = pq_primitives.decapsulate(
        recipient_kem_private,
        ciphertext.kem_ciphertext,
        pq_primitives.PQ_KEM,
    )

    # Derive decryption key
    hkdf = HKDF(
        algorithm=hashes.SHA256(),
        length=PQ_KEY_SIZE,
        salt=None,
        info=PQ_INFO,
    )
    decryption_key = hkdf.derive(shared_secret)

    # Decrypt with AES-GCM
    aesgcm = AESGCM(decryption_key)
    return aesgcm.decrypt(ciphertext.nonce, ciphertext.ciphertext, None)
