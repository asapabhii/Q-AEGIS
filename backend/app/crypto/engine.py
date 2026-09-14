"""Byte-level encryption for the three protection profiles, ``SPEC.md`` 3.7.

Profiles:
- ``aes256``: AES-256-GCM via ``cryptography``.
- ``hybrid``: ``X25519MLKEM768`` (X25519 ECDH + ML-KEM-768 combined with HKDF).
- ``post_quantum``: ML-KEM-1024 plus ML-DSA-87 via ``liboqs-python``.

Hybrid and post-quantum encryption fail closed when liboqs is unavailable.
The hybrid/PQ data-encryption key is derived from the KEM (and X25519) shared
secret(s); it is never an unrelated random key.

SECURITY CAVEAT: liboqs is NOT independently audited, and OQS-OpenSSL is
documented by its own maintainers as development and interop-testing only, not
production-supported. Do not claim audited-grade or FIPS-certified guarantees
that the library does not back up.
"""

from __future__ import annotations

import os
import struct

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric.x25519 import (
    X25519PrivateKey,
    X25519PublicKey,
)
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    NoEncryption,
    PrivateFormat,
    PublicFormat,
)

from app.crypto.exceptions import CryptoDecryptError
from app.crypto.key_management import (
    DEK_SIZE,
    WRAP_VERSION_AES256,
    WRAP_VERSION_HYBRID,
    WRAP_VERSION_POST_QUANTUM,
    wrap_dek,
    unwrap_dek,
)
from app.crypto.oqs_support import (
    ML_DSA_87,
    ML_KEM_1024,
    ML_KEM_768,
    require_oqs_for_profile,
)
from app.crypto.schemas import EncryptResult
from app.db.enums import CryptoProfileType

ALGORITHM_AES256 = "AES-256-GCM"
ALGORITHM_HYBRID = "X25519MLKEM768+AES-256-GCM"
ALGORITHM_POST_QUANTUM = "ML-KEM-1024+ML-DSA-87+AES-256-GCM"

HYBRID_KDF_SALT = b"qaegis-shield-hybrid-x25519mlkem768-v1"
HYBRID_KDF_INFO = b"qaegis-shield-hybrid-dek-v1"
PQ_KDF_SALT = b"qaegis-shield-mlkem1024-v1"
PQ_KDF_INFO = b"qaegis-shield-pq-dek-v1"

X25519_PUBLIC_KEY_SIZE = 32
ML_KEM_1024_CIPHERTEXT_SIZE = 1568


def _x25519_public_raw(key: X25519PublicKey) -> bytes:
    """Serialize an X25519 public key.

    SECURITY CAVEAT: liboqs is NOT independently audited.
    """
    return key.public_bytes(Encoding.Raw, PublicFormat.Raw)


def _x25519_private_raw(key: X25519PrivateKey) -> bytes:
    """Serialize an X25519 private key.

    SECURITY CAVEAT: liboqs is NOT independently audited.
    """
    return key.private_bytes(Encoding.Raw, PrivateFormat.Raw, NoEncryption())


def _ml_kem_secret_key_length(algorithm: str) -> int:
    """Return the secret-key length for one ML-KEM algorithm.

    SECURITY CAVEAT: liboqs is NOT independently audited.
    """
    import oqs

    with oqs.KeyEncapsulation(algorithm) as kem:
        kem.generate_keypair()
        return len(kem.export_secret_key())


def _ml_dsa_secret_key_length() -> int:
    """Return the ML-DSA-87 secret-key length.

    SECURITY CAVEAT: liboqs is NOT independently audited.
    """
    import oqs

    with oqs.Signature(ML_DSA_87) as signer:
        signer.generate_keypair()
        return len(signer.export_secret_key())


def encrypt_document_bytes(
    plaintext: bytes,
    profile_type: CryptoProfileType,
    *,
    master_key: bytes | None = None,
) -> EncryptResult:
    """Encrypt document bytes with the selected protection profile.

    SECURITY CAVEAT: liboqs is NOT independently audited. Hybrid and
    post-quantum profiles require liboqs and fail closed when it is missing.

    Args:
        plaintext: Raw document content.
        profile_type: One of ``aes256``, ``hybrid``, or ``post_quantum``.
        master_key: Optional master key override for tests.

    Returns:
        Ciphertext material including a master-key-wrapped secret payload for
        shredding.

    Raises:
        LiboqsUnavailableError: when hybrid or post-quantum is requested without
            liboqs.
        CryptoConfigurationError: when ``CRYPTO_MASTER_KEY`` is missing.
    """
    if profile_type == CryptoProfileType.AES256:
        return _encrypt_aes256(plaintext, master_key=master_key)
    require_oqs_for_profile(profile_type)
    if profile_type == CryptoProfileType.HYBRID:
        return _encrypt_hybrid(plaintext, master_key=master_key)
    return _encrypt_post_quantum(plaintext, master_key=master_key)


def decrypt_document_bytes(
    result: EncryptResult,
    profile_type: CryptoProfileType,
    *,
    master_key: bytes | None = None,
) -> bytes:
    """Decrypt bytes produced by :func:`encrypt_document_bytes`.

    SECURITY CAVEAT: liboqs is NOT independently audited.

    Args:
        result: Encryption output including wrapped secrets and optional KEM data.
        profile_type: Profile used during encryption.
        master_key: Optional master key override for tests.

    Returns:
        The original plaintext bytes.

    Raises:
        LiboqsUnavailableError: when hybrid or post-quantum decryption needs liboqs.
        CryptoDecryptError: when authentication or signature verification fails.
    """
    try:
        if profile_type == CryptoProfileType.AES256:
            return _decrypt_aes256(result, master_key=master_key)
        require_oqs_for_profile(profile_type)
        if profile_type == CryptoProfileType.HYBRID:
            return _decrypt_hybrid(result, master_key=master_key)
        return _decrypt_post_quantum(result, master_key=master_key)
    except InvalidTag as exc:
        raise CryptoDecryptError(
            "Ciphertext or wrapped key authentication failed."
        ) from exc


def _encrypt_aes_gcm(dek: bytes, plaintext: bytes) -> tuple[bytes, bytes]:
    """AES-256-GCM encrypt. SECURITY CAVEAT: liboqs is NOT independently audited."""
    nonce = os.urandom(12)
    ciphertext = AESGCM(dek).encrypt(nonce, plaintext, None)
    return nonce, ciphertext


def _decrypt_aes_gcm(dek: bytes, nonce: bytes, ciphertext: bytes) -> bytes:
    """AES-256-GCM decrypt. SECURITY CAVEAT: liboqs is NOT independently audited.

    Raises:
        InvalidTag: on authentication failure (normalized at the public boundary).
    """
    return AESGCM(dek).decrypt(nonce, ciphertext, None)


def _encrypt_aes256(plaintext: bytes, *, master_key: bytes | None) -> EncryptResult:
    """AES-256-GCM with a random DEK wrapped under the master key.

    SECURITY CAVEAT: liboqs is NOT independently audited.
    """
    dek = os.urandom(DEK_SIZE)
    nonce, ciphertext = _encrypt_aes_gcm(dek, plaintext)
    payload = bytes([WRAP_VERSION_AES256]) + dek
    return EncryptResult(
        ciphertext=ciphertext,
        nonce=nonce,
        wrapped_dek=wrap_dek(payload, master_key=master_key),
        kem_ciphertext=None,
        algorithm=ALGORITHM_AES256,
    )


def _decrypt_aes256(result: EncryptResult, *, master_key: bytes | None) -> bytes:
    """Decrypt AES-256 profile. SECURITY CAVEAT: liboqs is NOT independently audited."""
    if result.algorithm != ALGORITHM_AES256:
        raise CryptoDecryptError(
            f"Expected algorithm {ALGORITHM_AES256}, got {result.algorithm!r}."
        )
    payload = unwrap_dek(result.wrapped_dek, master_key=master_key)
    if len(payload) != 1 + DEK_SIZE or payload[0] != WRAP_VERSION_AES256:
        raise CryptoDecryptError("Invalid AES-256 wrapped DEK payload.")
    dek = payload[1:]
    return _decrypt_aes_gcm(dek, result.nonce, result.ciphertext)


def _derive_hybrid_secret(ml_kem_shared: bytes, x25519_shared: bytes) -> bytes:
    """HKDF the X25519MLKEM768 shared secrets into a DEK.

    SECURITY CAVEAT: liboqs is NOT independently audited.
    """
    return HKDF(
        algorithm=hashes.SHA256(),
        length=DEK_SIZE,
        salt=HYBRID_KDF_SALT,
        info=HYBRID_KDF_INFO,
    ).derive(ml_kem_shared + x25519_shared)


def _derive_pq_secret(ml_kem_shared: bytes) -> bytes:
    """HKDF the ML-KEM-1024 shared secret into a DEK.

    SECURITY CAVEAT: liboqs is NOT independently audited.
    """
    return HKDF(
        algorithm=hashes.SHA256(),
        length=DEK_SIZE,
        salt=PQ_KDF_SALT,
        info=PQ_KDF_INFO,
    ).derive(ml_kem_shared)


def _encrypt_hybrid(plaintext: bytes, *, master_key: bytes | None) -> EncryptResult:
    """X25519MLKEM768: DEK is HKDF(ML-KEM-768 || X25519), not a random key.

    SECURITY CAVEAT: liboqs is NOT independently audited.
    """
    import oqs

    recipient_x25519 = X25519PrivateKey.generate()
    recipient_x25519_public = _x25519_public_raw(recipient_x25519.public_key())
    ephemeral_x25519 = X25519PrivateKey.generate()
    ephemeral_x25519_public = _x25519_public_raw(ephemeral_x25519.public_key())

    with oqs.KeyEncapsulation(ML_KEM_768) as kem:
        ml_kem_public = kem.generate_keypair()
        ml_kem_secret = kem.export_secret_key()
        with oqs.KeyEncapsulation(ML_KEM_768) as encapsulator:
            kem_ciphertext, ml_kem_shared = encapsulator.encap_secret(ml_kem_public)

    x25519_shared = ephemeral_x25519.exchange(
        X25519PublicKey.from_public_bytes(recipient_x25519_public)
    )
    dek = _derive_hybrid_secret(ml_kem_shared, x25519_shared)

    nonce, ciphertext = _encrypt_aes_gcm(dek, plaintext)
    # Wrap only the private material needed to re-derive the DEK. Destroying
    # this blob (FR-8) removes the ability to decap / ECDH, so the DEK is gone.
    payload = (
        bytes([WRAP_VERSION_HYBRID])
        + ml_kem_secret
        + _x25519_private_raw(recipient_x25519)
    )
    kem_blob = ephemeral_x25519_public + kem_ciphertext + recipient_x25519_public
    return EncryptResult(
        ciphertext=ciphertext,
        nonce=nonce,
        wrapped_dek=wrap_dek(payload, master_key=master_key),
        kem_ciphertext=kem_blob,
        algorithm=ALGORITHM_HYBRID,
    )


def _decrypt_hybrid(result: EncryptResult, *, master_key: bytes | None) -> bytes:
    """Decrypt hybrid profile by re-deriving the DEK from KEM + X25519.

    SECURITY CAVEAT: liboqs is NOT independently audited.
    """
    import oqs

    if result.algorithm != ALGORITHM_HYBRID or result.kem_ciphertext is None:
        raise CryptoDecryptError(
            "Hybrid decryption requires hybrid algorithm and KEM data."
        )

    if len(result.kem_ciphertext) < (X25519_PUBLIC_KEY_SIZE * 2) + 1:
        raise CryptoDecryptError("Hybrid KEM blob is too short.")

    ephemeral_public = result.kem_ciphertext[:X25519_PUBLIC_KEY_SIZE]
    kem_ciphertext = result.kem_ciphertext[
        X25519_PUBLIC_KEY_SIZE:-X25519_PUBLIC_KEY_SIZE
    ]

    payload = unwrap_dek(result.wrapped_dek, master_key=master_key)
    if payload[0] != WRAP_VERSION_HYBRID:
        raise CryptoDecryptError("Invalid hybrid wrapped DEK payload version.")

    ml_kem_secret_len = _ml_kem_secret_key_length(ML_KEM_768)
    expected_len = 1 + ml_kem_secret_len + X25519_PUBLIC_KEY_SIZE
    if len(payload) != expected_len:
        raise CryptoDecryptError("Invalid hybrid wrapped DEK payload length.")

    ml_kem_secret = payload[1 : 1 + ml_kem_secret_len]
    recipient_secret = payload[1 + ml_kem_secret_len :]

    with oqs.KeyEncapsulation(ML_KEM_768, ml_kem_secret) as kem:
        ml_kem_shared = kem.decap_secret(kem_ciphertext)

    recipient_x25519 = X25519PrivateKey.from_private_bytes(recipient_secret)
    x25519_shared = recipient_x25519.exchange(
        X25519PublicKey.from_public_bytes(ephemeral_public)
    )
    dek = _derive_hybrid_secret(ml_kem_shared, x25519_shared)

    return _decrypt_aes_gcm(dek, result.nonce, result.ciphertext)


def _pack_post_quantum_kem(
    kem_ciphertext: bytes, signature: bytes, verify_public_key: bytes
) -> bytes:
    """Pack PQ envelope bytes. SECURITY CAVEAT: liboqs is NOT independently audited."""
    return (
        kem_ciphertext
        + struct.pack(">H", len(signature))
        + signature
        + verify_public_key
    )


def _unpack_post_quantum_kem(blob: bytes) -> tuple[bytes, bytes, bytes]:
    """Unpack PQ envelope. SECURITY CAVEAT: liboqs is NOT independently audited."""
    minimum = ML_KEM_1024_CIPHERTEXT_SIZE + 2
    if len(blob) < minimum:
        raise CryptoDecryptError("Post-quantum KEM blob is too short.")
    kem_ciphertext = blob[:ML_KEM_1024_CIPHERTEXT_SIZE]
    offset = ML_KEM_1024_CIPHERTEXT_SIZE
    signature_len = struct.unpack(">H", blob[offset : offset + 2])[0]
    signature = blob[offset + 2 : offset + 2 + signature_len]
    verify_public_key = blob[offset + 2 + signature_len :]
    if not verify_public_key or len(signature) != signature_len:
        raise CryptoDecryptError("Invalid post-quantum signature envelope.")
    return kem_ciphertext, signature, verify_public_key


def _encrypt_post_quantum(
    plaintext: bytes, *, master_key: bytes | None
) -> EncryptResult:
    """ML-KEM-1024 DEK derivation + ML-DSA-87 over ciphertext metadata.

    SECURITY CAVEAT: liboqs is NOT independently audited. The DEK is HKDF of
    the ML-KEM shared secret, not an unrelated random key.
    """
    import oqs

    with oqs.KeyEncapsulation(ML_KEM_1024) as kem:
        ml_kem_public = kem.generate_keypair()
        ml_kem_secret = kem.export_secret_key()
        with oqs.KeyEncapsulation(ML_KEM_1024) as encapsulator:
            kem_ciphertext, ml_kem_shared = encapsulator.encap_secret(ml_kem_public)

    dek = _derive_pq_secret(ml_kem_shared)
    nonce, ciphertext = _encrypt_aes_gcm(dek, plaintext)

    sign_message = result_signing_input(nonce, ciphertext, kem_ciphertext)
    with oqs.Signature(ML_DSA_87) as signer:
        sign_public = signer.generate_keypair()
        sign_secret = signer.export_secret_key()
        signature = signer.sign(sign_message)

    payload = bytes([WRAP_VERSION_POST_QUANTUM]) + ml_kem_secret + sign_secret
    kem_blob = _pack_post_quantum_kem(kem_ciphertext, signature, sign_public)
    return EncryptResult(
        ciphertext=ciphertext,
        nonce=nonce,
        wrapped_dek=wrap_dek(payload, master_key=master_key),
        kem_ciphertext=kem_blob,
        algorithm=ALGORITHM_POST_QUANTUM,
    )


def _decrypt_post_quantum(result: EncryptResult, *, master_key: bytes | None) -> bytes:
    """Decrypt PQ profile by re-deriving the DEK from ML-KEM-1024.

    SECURITY CAVEAT: liboqs is NOT independently audited.
    """
    import oqs

    if result.algorithm != ALGORITHM_POST_QUANTUM or result.kem_ciphertext is None:
        raise CryptoDecryptError(
            "Post-quantum decryption requires post-quantum algorithm and KEM data."
        )

    kem_ciphertext, signature, sign_public = _unpack_post_quantum_kem(
        result.kem_ciphertext
    )
    sign_message = result_signing_input(result.nonce, result.ciphertext, kem_ciphertext)

    with oqs.Signature(ML_DSA_87) as verifier:
        if not verifier.verify(sign_message, signature, sign_public):
            raise CryptoDecryptError("ML-DSA-87 signature verification failed.")

    payload = unwrap_dek(result.wrapped_dek, master_key=master_key)
    if payload[0] != WRAP_VERSION_POST_QUANTUM:
        raise CryptoDecryptError("Invalid post-quantum wrapped DEK payload version.")

    ml_kem_secret_len = _ml_kem_secret_key_length(ML_KEM_1024)
    sign_secret_len = _ml_dsa_secret_key_length()

    expected_len = 1 + ml_kem_secret_len + sign_secret_len
    if len(payload) != expected_len:
        raise CryptoDecryptError("Invalid post-quantum wrapped DEK payload length.")

    ml_kem_secret = payload[1 : 1 + ml_kem_secret_len]
    # sign_secret retained for shredding completeness; verification uses public key.
    _ = payload[1 + ml_kem_secret_len :]

    with oqs.KeyEncapsulation(ML_KEM_1024, ml_kem_secret) as kem:
        ml_kem_shared = kem.decap_secret(kem_ciphertext)
    dek = _derive_pq_secret(ml_kem_shared)

    return _decrypt_aes_gcm(dek, result.nonce, result.ciphertext)


def result_signing_input(
    nonce: bytes, ciphertext: bytes, kem_ciphertext: bytes
) -> bytes:
    """Canonical bytes signed by ML-DSA-87 for post-quantum ciphertexts.

    SECURITY CAVEAT: liboqs is NOT independently audited.
    """
    return nonce + ciphertext + kem_ciphertext
