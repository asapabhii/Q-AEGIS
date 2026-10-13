"""``audit_signing_keys`` and ``audit_checkpoints`` — PQ-signed Signed Tree Heads.

``SPEC.md`` 3.8, ``PRD.md`` FR-7. These two tables turn the Merkle root that
:mod:`app.audit.merkle` recomputes into an *externally verifiable* commitment.

``audit_checkpoints`` stores one Signed Tree Head per issuance: the
``merkle_root`` over a chain's prefix of ``tree_size`` leaves, an ML-DSA-87
``signature`` over the canonical bytes of :func:`app.audit.checkpoint`, and the
``signed_at`` time folded into those bytes. ``audit_signing_keys`` holds the
keypairs that sign them: the public key in the clear (auditors pin it), the
secret key wrapped under ``CRYPTO_MASTER_KEY`` so it is useless without the
master secret.

Both tables are append-only against UPDATE, DELETE, and TRUNCATE, enforced by
the same database triggers as ``audit_log`` (see the migration and
:mod:`app.db.models`). A checkpoint and the key that signed it are evidence; the
guarantee the checkpoint exists to provide is defeated the moment either can be
rewritten or quietly removed. The "active" signing key is simply the most recent
row, so rotation is an INSERT and no UPDATE of a mutable flag is ever needed —
which is what keeps the key table append-only.

SECURITY CAVEAT: liboqs is NOT independently audited, and OQS-OpenSSL is
documented by its own maintainers as development and interop-testing only, not
production-supported. Key management this phase is environment-configured
secrets, not a hardware security module (``PRD.md`` NG5).
"""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CHAR, ForeignKey, Integer, LargeBinary, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base, created_timestamp, uuid_primary_key

#: Length of a hex-encoded SHA-256 Merkle root, matching ``audit_log``.
HASH_HEX_LENGTH = 64


class AuditSigningKey(Base):
    """One ML-DSA-87 keypair used to sign audit checkpoints.

    APPEND-ONLY against UPDATE, DELETE, and TRUNCATE. The secret key is wrapped
    under the master key before it reaches this table, so a database read alone
    never yields signing capability. The public key is stored in the clear
    precisely so it can be published and pinned by auditors.

    The active key is the row with the newest ``created_at``; rotation inserts a
    new row rather than mutating a flag, which is what lets this table stay
    append-only. Superseded keys are retained so a historical checkpoint stays
    verifiable against the key that actually signed it.
    """

    __tablename__ = "audit_signing_keys"

    id: Mapped[UUID] = uuid_primary_key()
    # The liboqs mechanism name, e.g. "ML-DSA-87". Recorded per row so a future
    # algorithm rotation is attributable and a verifier knows which primitive to
    # use without guessing from key length.
    algorithm: Mapped[str] = mapped_column(String(32), nullable=False)
    # Raw ML-DSA-87 public key, hex-encoded. Not a secret; published for pinning.
    public_key: Mapped[str] = mapped_column(Text, nullable=False)
    # The ML-DSA-87 secret key wrapped under CRYPTO_MASTER_KEY
    # (app.crypto.key_management.wrap_dek). Bytea, not hex text: it never leaves
    # the server and never appears in an API response, so there is nothing to
    # gain from a text encoding.
    wrapped_secret_key: Mapped[bytes] = mapped_column(LargeBinary, nullable=False)
    created_at: Mapped[datetime] = created_timestamp(index=True)


class AuditCheckpoint(Base):
    """One Signed Tree Head: a signed commitment to a chain's root at a time.

    APPEND-ONLY against UPDATE, DELETE, and TRUNCATE. Each row commits to the
    Merkle root over the prefix of ``tree_size`` leaves of one chain
    (``document_id``, or null for the system chain), signed with the key named by
    ``signing_key_id``. The signature covers the canonical bytes of
    :func:`app.audit.checkpoint.checkpoint_signing_input`, which bind
    ``document_id``, ``tree_size``, ``signed_at``, and ``merkle_root`` together;
    changing any of them invalidates the signature.

    ``merkle_root`` is stored for convenience and export, never trusted as a
    verdict: verification recomputes the root from the stored payloads and checks
    it matches, exactly as the rest of the audit layer does.
    """

    __tablename__ = "audit_checkpoints"

    id: Mapped[UUID] = uuid_primary_key()
    document_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("documents.id", ondelete="RESTRICT"),
        # Null for the system chain of document-less events, mirroring audit_log.
        nullable=True,
        index=True,
    )
    signing_key_id: Mapped[UUID] = mapped_column(
        ForeignKey("audit_signing_keys.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    # Number of leaves the root covers: the prefix 0..tree_size-1. A checkpoint
    # over an older, smaller prefix stays valid forever, which is what lets an
    # auditor anchor a root now and prove non-rewriting against it later.
    tree_size: Mapped[int] = mapped_column(Integer, nullable=False)
    merkle_root: Mapped[str] = mapped_column(CHAR(HASH_HEX_LENGTH), nullable=False)
    # Detached ML-DSA-87 signature, hex-encoded, over the canonical signing input.
    # Text rather than bytea because this value is exported to auditors in JSON;
    # hex keeps the API boundary free of base64/binary handling.
    signature: Mapped[str] = mapped_column(Text, nullable=False)
    # When the checkpoint was issued. This exact value is folded into the signed
    # bytes, so it is part of the commitment, not incidental metadata.
    signed_at: Mapped[datetime] = created_timestamp(index=True)
    created_at: Mapped[datetime] = created_timestamp()
