"""PQ-signed audit checkpoints (Signed Tree Heads), ``SPEC.md`` 3.8, ``PRD.md`` FR-7.

A Merkle root recomputed from stored payloads proves the chain is internally
consistent, but not that it was not *rewritten* wholesale: an operator with
write access could rebuild an entirely new chain and a fresh set of roots.
``docs/data-dictionary.md`` and every audit docstring state this limit plainly.
What closes it is an externally verifiable commitment to a root at a point in
time that the operator cannot forge after the fact.

This module produces that commitment: a **Signed Tree Head** in the RFC 6962
§3.5 sense, adapted to this system's per-document chains. A checkpoint binds

    (schema version, document_id, tree_size, signed_at, merkle_root)

into one canonical byte string and signs it with **ML-DSA-87** (the same
NIST level-5 signature the post-quantum protection profile uses). An auditor who
has pinned the log's public key out-of-band can verify offline that this system
committed to exactly that root, for exactly that prefix, at exactly that time.
Rewriting history later would require re-signing every superseded checkpoint with
the private key, which the operator does not hold once it is destroyed or held by
a separate custodian, and cannot forge under ML-DSA-87.

Purity, exactly as in :mod:`app.audit.merkle`: the functions here do no I/O and
touch no database. Signing needs a secret key handed in; verification needs a
public key and the signed bytes. The service layer
(:mod:`app.audit.service`) is what loads chains, recomputes roots, and unwraps
the persisted signing key; the persistence lives in
:mod:`app.db.repositories.checkpoint`. Keeping the crypto pure is what lets an
auditor re-run :func:`verify_checkpoint_signature` against an exported checkpoint
and a pinned key, trusting nothing this system stored.

SECURITY CAVEAT, restated per the crypto package convention: liboqs is NOT
independently audited, and OQS-OpenSSL is documented by its own maintainers as
development and interop-testing only, not production-supported. Key management
this phase is environment-configured secrets (the signing secret is wrapped under
``CRYPTO_MASTER_KEY``), NOT a hardware security module (``PRD.md`` NG5). Do not
describe these checkpoints as hardware-backed or FIPS-certified.
"""

from __future__ import annotations

import struct
from datetime import datetime, timezone
from uuid import UUID

from app.crypto.oqs_support import ML_DSA_87, require_oqs_for_signature

#: ML-DSA-87, NIST level 5. The signature algorithm for every checkpoint. Pinned
#: here and recorded on every row so a future rotation to a different algorithm
#: is an explicit, attributable change rather than a silent one.
CHECKPOINT_SIGNATURE_ALGORITHM = ML_DSA_87

#: Domain-separation tag. Prefixing the signed bytes with a constant that names
#: this exact use means a signature produced here can never be replayed as a
#: signature over anything else in the system (a ciphertext envelope, a token),
#: and vice versa. The trailing version marker lets the signed structure evolve
#: without a verifier ever confusing two layouts.
CHECKPOINT_DOMAIN = b"qaegis-audit-sth-v1"

#: Schema version of the signed structure, folded into the signed bytes so a
#: layout change cannot be passed off as the old layout.
CHECKPOINT_STRUCT_VERSION = 1

#: Length of a hex-encoded SHA-256 Merkle root.
_ROOT_HEX_LENGTH = 64

_EPOCH = datetime(1970, 1, 1, tzinfo=timezone.utc)


def _epoch_micros(moment: datetime) -> int:
    """Return integer microseconds since the Unix epoch, in UTC.

    Integer arithmetic on a ``timedelta``, never ``timestamp() * 1e6``: the float
    path can drift by a microsecond, and a signed structure that does not
    reproduce bit-for-bit on the way back is a signature that fails to verify for
    an untampered checkpoint. A naive datetime is treated as UTC rather than
    guessed at.
    """
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=timezone.utc)
    delta = moment.astimezone(timezone.utc) - _EPOCH
    return (delta.days * 86_400 + delta.seconds) * 1_000_000 + delta.microseconds


def checkpoint_signing_input(
    *,
    document_id: UUID | None,
    tree_size: int,
    signed_at: datetime,
    merkle_root: str,
) -> bytes:
    """Serialise a checkpoint into the exact bytes that get signed.

    The layout is fully unambiguous: after the domain tag and a version byte,
    every field is fixed-width or self-delimiting, so no two distinct checkpoints
    can ever produce the same bytes (no length-prefix confusion, no separator that
    could appear inside a field).

    Layout::

        CHECKPOINT_DOMAIN
        version           : 1 byte
        document flag      : 1 byte  (0 = system chain / None, 1 = present)
        document_id        : 16 bytes, present only when the flag is 1
        tree_size          : 8 bytes, unsigned big-endian
        signed_at          : 8 bytes, signed big-endian microseconds since epoch
        merkle_root        : 32 raw bytes (the hex root decoded)

    Args:
        document_id: The chain the checkpoint commits to, or ``None`` for the
            system chain of events with no document.
        tree_size: Number of leaves the root covers (the prefix ``0..size-1``).
        signed_at: When the checkpoint was issued. Normalised to UTC.
        merkle_root: The 64-char hex Merkle root over that prefix.

    Returns:
        The canonical bytes to sign or verify.

    Raises:
        ValueError: if ``tree_size`` is negative or ``merkle_root`` is not a
            64-character hex string.
    """
    if tree_size < 0:
        raise ValueError(f"tree_size must be non-negative, got {tree_size}.")
    if len(merkle_root) != _ROOT_HEX_LENGTH:
        raise ValueError(
            f"merkle_root must be {_ROOT_HEX_LENGTH} hex chars, "
            f"got {len(merkle_root)}."
        )
    try:
        root_bytes = bytes.fromhex(merkle_root)
    except ValueError as exc:
        raise ValueError("merkle_root must be valid hexadecimal.") from exc

    if document_id is None:
        document_part = b"\x00"
    else:
        document_part = b"\x01" + document_id.bytes

    return (
        CHECKPOINT_DOMAIN
        + bytes([CHECKPOINT_STRUCT_VERSION])
        + document_part
        + struct.pack(">Q", tree_size)
        + struct.pack(">q", _epoch_micros(signed_at))
        + root_bytes
    )


def generate_signing_keypair() -> tuple[bytes, bytes]:
    """Generate one ML-DSA-87 keypair for signing checkpoints.

    SECURITY CAVEAT: liboqs is NOT independently audited.

    Returns:
        ``(public_key, secret_key)`` as raw bytes. The caller wraps the secret
        under the master key before it is persisted; the public key is published
        so auditors can pin it.

    Raises:
        LiboqsUnavailableError: when liboqs or ML-DSA-87 is unavailable.
    """
    require_oqs_for_signature(CHECKPOINT_SIGNATURE_ALGORITHM)
    import oqs

    with oqs.Signature(CHECKPOINT_SIGNATURE_ALGORITHM) as signer:
        public_key = signer.generate_keypair()
        secret_key = signer.export_secret_key()
    return public_key, secret_key


def sign_checkpoint(signing_input: bytes, secret_key: bytes) -> bytes:
    """Sign the canonical checkpoint bytes with an ML-DSA-87 secret key.

    SECURITY CAVEAT: liboqs is NOT independently audited.

    Args:
        signing_input: Output of :func:`checkpoint_signing_input`.
        secret_key: Raw ML-DSA-87 secret key (unwrapped by the service layer).

    Returns:
        The detached signature bytes.

    Raises:
        LiboqsUnavailableError: when liboqs or ML-DSA-87 is unavailable.
    """
    require_oqs_for_signature(CHECKPOINT_SIGNATURE_ALGORITHM)
    import oqs

    with oqs.Signature(CHECKPOINT_SIGNATURE_ALGORITHM, secret_key) as signer:
        return signer.sign(signing_input)


def verify_checkpoint_signature(
    signing_input: bytes, signature: bytes, public_key: bytes
) -> bool:
    """Verify an ML-DSA-87 checkpoint signature. Pure w.r.t. this system's state.

    This is the function an auditor runs offline: given the checkpoint's fields
    (from which they rebuild ``signing_input`` with
    :func:`checkpoint_signing_input`), the signature, and a public key they
    pinned independently, it answers whether this log committed to that root at
    that time. It reads nothing this system stored as a verdict.

    SECURITY CAVEAT: liboqs is NOT independently audited.

    Args:
        signing_input: Canonical bytes rebuilt from the checkpoint's fields.
        signature: The detached signature to check.
        public_key: The log's pinned ML-DSA-87 public key.

    Returns:
        True only if the signature is valid for that input under that key.

    Raises:
        LiboqsUnavailableError: when liboqs or ML-DSA-87 is unavailable.
    """
    require_oqs_for_signature(CHECKPOINT_SIGNATURE_ALGORITHM)
    import oqs

    with oqs.Signature(CHECKPOINT_SIGNATURE_ALGORITHM) as verifier:
        return bool(verifier.verify(signing_input, signature, public_key))
