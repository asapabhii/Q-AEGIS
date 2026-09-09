"""Crypto-shredding for right-to-erasure compliance, `SPEC.md` 3.9, `PRD.md` FR-8.

STUB IMPLEMENTATION: Key destruction is simulated as no real key material
exists in this phase (`PRD.md` NG4/NG5). The endpoint writes an
`erasure_requested` audit log entry and advances the document's lifecycle
status to `ARCHIVED`.

SECURITY CAVEAT: liboqs is NOT independently audited, and OQS-OpenSSL is
documented by its own maintainers as development and interop-testing only,
not production-supported. Do not claim audited-grade or FIPS-certified
guarantees that the library does not back up.
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID


@dataclass(frozen=True)
class ShredResult:
    """Result of a crypto-shredding operation.

    Attributes:
        document_id: UUID of the document whose key was shredded.
        actor_id: UUID of the user who confirmed the shredding.
        shredded_at: Timestamp when the shredding occurred.
    """

    document_id: UUID
    actor_id: UUID
    shredded_at: datetime


def shred_document_key(document_id: UUID, actor_id: UUID) -> ShredResult:
    """Simulate cryptographic erasure of a document's encryption key.

    This is a STUB implementation. In Phase 1, key material does not exist
    (`PRD.md` NG4/NG5), so this function simulates the shredding by:
    1. Recording the shred request with a timestamp
    2. The actual key destruction will be implemented in Phase 3

    PRD FR-8 requires:
    - "Erasure destroys the document's encryption key, not the audit log"
    - "Key destruction is irreversible once confirmed, no recovery path"
    - Audit log entry MUST exist proving the request was honored

    Args:
        document_id: UUID of the document to shred.
        actor_id: UUID of the user who confirmed the shredding.

    Returns:
        ShredResult with the document_id, actor_id, and timestamp.
    """
    return ShredResult(
        document_id=document_id,
        actor_id=actor_id,
        shredded_at=datetime.now(timezone.utc),
    )
