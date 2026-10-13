"""Crypto-shredding: destruction of wrapped DEKs, ``SPEC.md`` 3.9.

``PRD.md`` FR-8: erasure destroys the document's encryption key material, not
the audit trail. Ciphertext rows remain as proof that data existed; once the
wrapped DEK is gone they cannot be decrypted through this system.

What "irreversible" means here, precisely: the wrapped DEK in the *live* row is
overwritten in place with a marker plus fresh randomness, and there is no
application path — no soft-delete, no undo window, no key escrow — to recover it
past the confirmation step. That is the guarantee the API makes and the audit
``irreversible`` flag asserts.

STORAGE REMANENCE CAVEAT: overwriting the live row does not by itself erase
every physical copy of the prior bytes. On PostgreSQL the pre-overwrite tuple
survives as a dead row version until ``VACUUM``, the change is written to the
write-ahead log, and both propagate to any streaming replica and to every base
backup / PITR archive taken before the shred. Cryptographic erasure is therefore
complete only once those copies have aged out under the deployment's vacuum, WAL
retention, replica, and backup-retention policies. This module performs the
logical destruction; closing the remanence window is an operational
responsibility of the platform those policies govern, and is out of scope for a
single request. It is documented in ``docs/data-dictionary.md`` and ``SPEC.md``
3.9 rather than silently implied away.

SECURITY CAVEAT: liboqs is NOT independently audited. Shredding applies to all
profiles, including hybrid and post-quantum rows that used liboqs.
"""

from __future__ import annotations

import os
from uuid import UUID

from sqlalchemy.orm import Session

from app.db.models import DocumentCiphertext
from app.db.repositories import ciphertexts as ciphertext_repo

#: Marker prefix written into ``wrapped_dek`` so shredded rows are detectable
#: without a schema change. Remaining bytes are random; unwrap always fails.
SHRED_MARKER = b"QAEGIS-SHREDDED\x00"


def is_shredded(wrapped_dek: bytes) -> bool:
    """Return whether ``wrapped_dek`` was overwritten by :func:`shred_wrapped_dek`.

    SECURITY CAVEAT: liboqs is NOT independently audited.
    """
    return wrapped_dek.startswith(SHRED_MARKER)


def shred_wrapped_dek(wrapped_dek: bytes) -> bytes:
    """Return replacement bytes that destroy one wrapped DEK.

    Same length as the original so the ``bytea`` column stays non-null. The
    marker plus fresh randomness replace every bit of the wrapped key, so the
    value stored in the live row can no longer be unwrapped. This is the
    in-application destruction; see the module docstring's storage-remanence
    caveat for why prior physical copies (MVCC, WAL, replicas, backups) are a
    separate, operational concern.

    SECURITY CAVEAT: liboqs is NOT independently audited.
    """
    if len(wrapped_dek) < len(SHRED_MARKER):
        raise ValueError("wrapped_dek is shorter than the shred marker")
    if is_shredded(wrapped_dek):
        return wrapped_dek
    pad_len = len(wrapped_dek) - len(SHRED_MARKER)
    return SHRED_MARKER + os.urandom(pad_len)


def shred_document_keys(
    session: Session, document_id: UUID
) -> tuple[list[DocumentCiphertext], int]:
    """Overwrite ``wrapped_dek`` on every ciphertext row for ``document_id``.

    Updates in place: shredding is the intentional exception to append-only
    history for key material. Ciphertext and nonce are left intact. Does not
    commit.

    SECURITY CAVEAT: liboqs is NOT independently audited.

    Returns:
        ``(rows, newly_destroyed)`` where ``newly_destroyed`` is how many rows
        were not already shredded before this call.
    """
    rows = ciphertext_repo.list_for_document(session, document_id, for_update=True)
    newly_destroyed = 0
    for row in rows:
        if is_shredded(row.wrapped_dek):
            continue
        row.wrapped_dek = shred_wrapped_dek(row.wrapped_dek)
        newly_destroyed += 1
    session.flush()
    return rows, newly_destroyed


def shred_audit_payload(
    *,
    document_id: UUID,
    ciphertext_ids: list[UUID],
    keys_destroyed: int,
    newly_destroyed: int,
) -> dict[str, object]:
    """Audit payload for one erasure. JSON primitives only.

    ``irreversible`` records that the wrapped DEK was overwritten with no
    application recovery path past confirmation; it is a statement about this
    system's behavior, not a claim that every physical copy of the prior bytes
    has already left the storage substrate (see the module docstring's
    storage-remanence caveat).

    SECURITY CAVEAT: liboqs is NOT independently audited.
    """
    return {
        "document_id": str(document_id),
        "ciphertext_ids": [str(item) for item in ciphertext_ids],
        "keys_destroyed": keys_destroyed,
        "newly_destroyed": newly_destroyed,
        "irreversible": True,
    }
