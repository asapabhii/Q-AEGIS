"""Crypto engine errors, ``SPEC.md`` 3.7.

SECURITY CAVEAT: liboqs is NOT independently audited, and OQS-OpenSSL is
documented by its own maintainers as development and interop-testing only, not
production-supported. Do not claim audited-grade or FIPS-certified guarantees
that the library does not back up.
"""


class CryptoConfigurationError(RuntimeError):
    """Raised when ``CRYPTO_MASTER_KEY`` is missing or malformed."""


class LiboqsUnavailableError(RuntimeError):
    """Raised when hybrid or post-quantum encryption is requested without liboqs.

    Hybrid and post-quantum profiles fail closed; they never fall back to AES-256.
    """


class CryptoDecryptError(RuntimeError):
    """Raised when ciphertext, wrapped keys, or signatures fail verification."""
