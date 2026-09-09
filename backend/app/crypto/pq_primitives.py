"""Post-quantum cryptography primitives, SPEC.md 3.7.

This module provides access to ML-KEM and ML-DSA algorithms via liboqs-python.
These are used by the hybrid and full post-quantum crypto profiles.

SECURITY CAVEAT: liboqs is NOT independently audited, and OQS-OpenSSL is
documented by its own maintainers as development and interop-testing only,
not production-supported. Do not claim audited-grade or FIPS-certified
guarantees that the library does not back up.

IMPORTANT: Never use retired names (CRYSTALS-Kyber, CRYSTALS-Dilithium) in code.
Use ML-KEM and ML-DSA per SPEC.md.
"""

#: KEM algorithms we use (per SPEC.md 3.7)
HYBRID_KEM = "ML-KEM-768"  # For hybrid profile
PQ_KEM = "ML-KEM-1024"  # For full post-quantum profile

#: Signature algorithms we use (per SPEC.md 3.7)
PQ_SIG = "ML-DSA-87"  # For full post-quantum profile

#: Whether liboqs native library is available
# Set this to True only when liboqs is properly installed with native binaries
OQS_AVAILABLE = False

#: liboqs version string
OQS_VERSION = None


def is_available() -> bool:
    """Check if liboqs is available and properly linked.

    Returns:
        True if liboqs native library is available, False otherwise.
    """
    return OQS_AVAILABLE


def get_version() -> str | None:
    """Get the liboqs version string.

    Returns:
        Version string or None if not available.
    """
    return OQS_VERSION


def _load_oqs():
    """Internal: try to load liboqs. Returns True if successful."""
    global OQS_AVAILABLE, OQS_VERSION
    if OQS_AVAILABLE:
        return True
    
    try:
        import oqs
        # Test if library actually loads
        _ = oqs.KEM.alg_names()
        OQS_AVAILABLE = True
        OQS_VERSION = oqs.__version__
        return True
    except Exception:
        return False


def list_kem_algorithms() -> list[str]:
    """List all available KEM (key encapsulation) algorithms.

    Returns:
        List of algorithm names.
    """
    if not _load_oqs():
        return []
    try:
        import oqs
        return oqs.KEM.alg_names()
    except Exception:
        return []


def list_sig_algorithms() -> list[str]:
    """List all available signature algorithms.

    Returns:
        List of algorithm names.
    """
    if not _load_oqs():
        return []
    try:
        import oqs
        return oqs.SIG.alg_names()
    except Exception:
        return []


def generate_kem_keypair(algorithm: str = HYBRID_KEM) -> tuple[bytes, bytes]:
    """Generate a KEM keypair.

    Args:
        algorithm: The KEM algorithm to use (default: ML-KEM-768).

    Returns:
        Tuple of (public_key, secret_key).

    Raises:
        RuntimeError: If liboqs is not available.
    """
    if not _load_oqs():
        raise RuntimeError(
            "liboqs is not available. Native library must be installed "
            "or set OQS_AVAILABLE=True after manual installation."
        )
    import oqs
    with oqs.KEM(algorithm) as kem:
        return kem.generate_keypair()


def encapsulate(public_key: bytes, algorithm: str = HYBRID_KEM) -> tuple[bytes, bytes]:
    """Encapsulate a shared secret using a public key.

    Args:
        public_key: The recipient's public key.
        algorithm: The KEM algorithm to use.

    Returns:
        Tuple of (ciphertext, shared_secret).

    Raises:
        RuntimeError: If liboqs is not available.
    """
    if not _load_oqs():
        raise RuntimeError(
            "liboqs is not available. Native library must be installed."
        )
    import oqs
    with oqs.KEM(algorithm) as kem:
        return kem.encapsulate(public_key)


def decapsulate(secret_key: bytes, ciphertext: bytes, algorithm: str = HYBRID_KEM) -> bytes:
    """Decapsulate a shared secret using a secret key.

    Args:
        secret_key: The recipient's secret key.
        ciphertext: The encapsulated shared secret.
        algorithm: The KEM algorithm to use.

    Returns:
        The shared secret.

    Raises:
        RuntimeError: If liboqs is not available.
    """
    if not _load_oqs():
        raise RuntimeError(
            "liboqs is not available. Native library must be installed."
        )
    import oqs
    with oqs.KEM(algorithm) as kem:
        return kem.decapsulate(secret_key, ciphertext)


def generate_sig_keypair(algorithm: str = PQ_SIG) -> tuple[bytes, bytes]:
    """Generate a signature keypair.

    Args:
        algorithm: The signature algorithm to use (default: ML-DSA-87).

    Returns:
        Tuple of (public_key, secret_key).

    Raises:
        RuntimeError: If liboqs is not available.
    """
    if not _load_oqs():
        raise RuntimeError(
            "liboqs is not available. Native library must be installed."
        )
    import oqs
    with oqs.SIG(algorithm) as sig:
        return sig.generate_keypair()


def sign(message: bytes, secret_key: bytes, algorithm: str = PQ_SIG) -> bytes:
    """Sign a message.

    Args:
        message: The message to sign.
        secret_key: The signer's secret key.
        algorithm: The signature algorithm to use.

    Returns:
        The signature.

    Raises:
        RuntimeError: If liboqs is not available.
    """
    if not _load_oqs():
        raise RuntimeError(
            "liboqs is not available. Native library must be installed."
        )
    import oqs
    with oqs.SIG(algorithm) as sig:
        return sig.sign(message, secret_key)


def verify(message: bytes, signature: bytes, public_key: bytes, algorithm: str = PQ_SIG) -> bool:
    """Verify a signature.

    Args:
        message: The original message.
        signature: The signature to verify.
        public_key: The signer's public key.
        algorithm: The signature algorithm to use.

    Returns:
        True if signature is valid, False otherwise.

    Raises:
        RuntimeError: If liboqs is not available.
    """
    if not _load_oqs():
        raise RuntimeError(
            "liboqs is not available. Native library must be installed."
        )
    import oqs
    with oqs.SIG(algorithm) as sig:
        return sig.verify(message, signature, public_key)
