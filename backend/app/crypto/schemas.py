"""Pydantic models for the crypto-profile API, ``SPEC.md`` 3.7.

No raw dicts cross this boundary. ``profile_type`` is computed from the
persisted trust score; the client cannot supply it. Extra keys are forbidden.

SECURITY CAVEAT: liboqs is NOT independently audited, and OQS-OpenSSL is
documented by its own maintainers as development and interop-testing only, not
production-supported. Do not claim audited-grade or FIPS-certified guarantees
that the library does not back up.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.db.enums import CryptoProfileType


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


class CryptoShredRequest(BaseModel):
    """Request to permanently shred a document's encryption key.

    ``document_id`` identifies the document to shred.
    """

    model_config = ConfigDict(extra="forbid")

    document_id: UUID


class CryptoShredResponse(BaseModel):
    """Response after successfully shredding a document's key."""

    document_id: UUID
    shredded_at: datetime
    status: str
