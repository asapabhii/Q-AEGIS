"""liboqs availability checks for hybrid and post-quantum profiles, ``SPEC.md`` 3.7.

SECURITY CAVEAT: liboqs is NOT independently audited, and OQS-OpenSSL is
documented by its own maintainers as development and interop-testing only, not
production-supported. Do not claim audited-grade or FIPS-certified guarantees
that the library does not back up.
"""

from __future__ import annotations

from app.crypto.exceptions import LiboqsUnavailableError
from app.db.enums import CryptoProfileType

ML_KEM_768 = "ML-KEM-768"
ML_KEM_1024 = "ML-KEM-1024"
ML_DSA_87 = "ML-DSA-87"


def oqs_available() -> bool:
    """Return whether ``liboqs-python`` is installed and its native library loads.

    SECURITY CAVEAT: liboqs is NOT independently audited.

    ``liboqs-python`` may attempt a source build on import when the shared
    library is missing; that path raises ``SystemExit`` on some platforms. This
    helper catches that and reports unavailable rather than aborting callers.
    """
    try:
        import oqs

        _ = oqs.get_enabled_kem_mechanisms()
    except BaseException:
        return False
    return True


def _enabled_kem_mechanisms() -> tuple[str, ...]:
    import oqs

    return tuple(oqs.get_enabled_kem_mechanisms())


def _enabled_sig_mechanisms() -> tuple[str, ...]:
    import oqs

    return tuple(oqs.get_enabled_sig_mechanisms())


def require_oqs_for_profile(profile_type: CryptoProfileType) -> None:
    """Refuse hybrid or post-quantum encryption when liboqs is unavailable.

    SECURITY CAVEAT: liboqs is NOT independently audited.

    AES-256 does not call this helper. Hybrid and post-quantum profiles fail
    closed and never silently fall back to classical AES.

    Args:
        profile_type: The protection profile about to be used.

    Raises:
        LiboqsUnavailableError: when ``profile_type`` needs liboqs and it is
            missing or lacks the required algorithms.
    """
    if profile_type == CryptoProfileType.AES256:
        return

    if not oqs_available():
        raise LiboqsUnavailableError(
            f"{profile_type.value} encryption requires liboqs-python, "
            "which is not installed."
        )

    if profile_type == CryptoProfileType.HYBRID:
        if ML_KEM_768 not in _enabled_kem_mechanisms():
            raise LiboqsUnavailableError(
                f"{profile_type.value} encryption requires {ML_KEM_768}, "
                "which is not enabled."
            )
        return

    if profile_type == CryptoProfileType.POST_QUANTUM:
        missing: list[str] = []
        if ML_KEM_1024 not in _enabled_kem_mechanisms():
            missing.append(ML_KEM_1024)
        if ML_DSA_87 not in _enabled_sig_mechanisms():
            missing.append(ML_DSA_87)
        if missing:
            raise LiboqsUnavailableError(
                f"{profile_type.value} encryption requires {', '.join(missing)}, "
                "which is not enabled."
            )
