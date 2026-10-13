"""Tamper-evident audit log, ``SPEC.md`` 3.8, implements ``PRD.md`` FR-7.

The Merkle core lives in :mod:`app.audit.merkle`: whole-log ``build`` /
``verify``, the incremental append frontier, and the RFC 6962 inclusion and
consistency proofs that let an auditor check one entry, or one growth step,
without re-reading the whole log. The append-only repository layer is in
:mod:`app.db.repositories.audit`, and prefix/proof verification services in
:mod:`app.audit.service`.

The PQ-signed checkpoint layer (:mod:`app.audit.checkpoint`) turns a recomputed
Merkle root into an externally verifiable Signed Tree Head: the pure ML-DSA-87
signing input, sign, and verify primitives live there; the orchestration that
loads a chain, recomputes its root, and persists a checkpoint is in
:mod:`app.audit.service`.

``audit_log`` is append-only. Never write an UPDATE or DELETE against it, in
application code or in a migration.
"""

from app.audit.checkpoint import (
    CHECKPOINT_DOMAIN,
    CHECKPOINT_SIGNATURE_ALGORITHM,
    CHECKPOINT_STRUCT_VERSION,
    checkpoint_signing_input,
    generate_signing_keypair,
    sign_checkpoint,
    verify_checkpoint_signature,
)
from app.audit.merkle import (
    EMPTY_ROOT,
    LEAF_PREFIX,
    NODE_PREFIX,
    ConsistencyProof,
    InclusionProof,
    MerkleTree,
    VerificationResult,
    build,
    canonicalize,
    consistency_proof,
    hash_internal,
    hash_leaf,
    inclusion_proof,
    verify,
    verify_consistency,
    verify_inclusion,
)

__all__ = [
    "CHECKPOINT_DOMAIN",
    "CHECKPOINT_SIGNATURE_ALGORITHM",
    "CHECKPOINT_STRUCT_VERSION",
    "EMPTY_ROOT",
    "LEAF_PREFIX",
    "NODE_PREFIX",
    "ConsistencyProof",
    "InclusionProof",
    "MerkleTree",
    "VerificationResult",
    "build",
    "canonicalize",
    "checkpoint_signing_input",
    "consistency_proof",
    "generate_signing_keypair",
    "hash_internal",
    "hash_leaf",
    "inclusion_proof",
    "sign_checkpoint",
    "verify",
    "verify_checkpoint_signature",
    "verify_consistency",
    "verify_inclusion",
]
