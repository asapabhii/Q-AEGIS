"""Tamper-evident audit log, ``SPEC.md`` 3.8, implements ``PRD.md`` FR-7.

Phase 1 provides the core Merkle tree functions only, see
:mod:`app.audit.merkle`. Still to build: the ``audit_log`` table with its
Postgres trigger rejecting UPDATE and DELETE, the append-only repository layer,
and inclusion proofs for single-entry verification.

``audit_log`` is append-only. Never write an UPDATE or DELETE against it, in
application code or in a migration.
"""

from app.audit.merkle import (
    EMPTY_ROOT,
    LEAF_PREFIX,
    NODE_PREFIX,
    MerkleTree,
    VerificationResult,
    build,
    canonicalize,
    hash_internal,
    hash_leaf,
    verify,
)

__all__ = [
    "EMPTY_ROOT",
    "LEAF_PREFIX",
    "NODE_PREFIX",
    "MerkleTree",
    "VerificationResult",
    "build",
    "canonicalize",
    "hash_internal",
    "hash_leaf",
    "verify",
]
