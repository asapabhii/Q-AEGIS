"""Pydantic models for the crypto engine and API, ``SPEC.md`` 3.7.

No raw dicts cross the API boundary. ``profile_type`` is computed from the
persisted trust score; the client cannot supply it. Extra keys are forbidden.

SECURITY CAVEAT: liboqs is NOT independently audited, and OQS-OpenSSL is
documented by its own maintainers as development and interop-testing only, not
production-supported. Do not claim audited-grade or FIPS-certified guarantees
that the library does not back up.
"""

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.db.enums import CryptoProfileType


@dataclass(frozen=True, slots=True)
class EncryptResult:
    """Byte-encryption output for one document.

    ``wrapped_dek`` is master-key-wrapped so crypto-shredding can destroy keys
    without deleting audit rows. ``kem_ciphertext`` holds profile-specific KEM
    or signature material and is null for AES-256.
    """

    ciphertext: bytes
    nonce: bytes
    wrapped_dek: bytes
    kem_ciphertext: bytes | None
    algorithm: str


class CryptoProfileRequest(BaseModel):
    """Select a protection profile from one persisted trust-score row.

    ``document_id`` is taken from that row. The client cannot supply it, and
    cannot supply ``profile_type``.
    """

    model_config = ConfigDict(extra="forbid")

    trust_score_id: UUID


class CryptoProfileResponse(BaseModel):
    """One persisted protection selection."""

    id: UUID
    document_id: UUID
    trust_score_id: UUID
    profile_type: CryptoProfileType
    consensus_value: Decimal
    selected_at: datetime
