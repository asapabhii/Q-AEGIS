"""Pydantic models for the contextual risk API, ``SPEC.md`` 3.3.

No raw dicts cross this boundary. ``risk_value`` is not a request field: the
server computes it. Extra keys are forbidden so a caller cannot smuggle
signals this version does not score.
"""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, field_validator

from app.risk_engine.scorer import ContextSnapshot, RiskScoreResult

#: Matches ``documents.filename``: a device identifier is caller-supplied text,
#: not an unbounded blob.
MAX_DEVICE_ID_CHARS = 255


class RiskScoreRequest(BaseModel):
    """A request to compute contextual risk for one registered document."""

    model_config = ConfigDict(extra="forbid")

    document_id: UUID
    actor_user_id: UUID
    device_id: str = Field(min_length=1, max_length=MAX_DEVICE_ID_CHARS)
    device_is_new: bool
    accessed_at: AwareDatetime
    after_hours: bool

    @field_validator("device_id")
    @classmethod
    def device_id_must_not_be_blank(cls, value: str) -> str:
        """Whitespace-only is not a device identity."""
        if not value.strip():
            raise ValueError(
                "device_id must contain at least one non-whitespace character"
            )
        return value

    def snapshot(self) -> ContextSnapshot:
        """The five snapshot fields, excluding ``document_id``."""
        return ContextSnapshot(
            actor_user_id=self.actor_user_id,
            device_id=self.device_id,
            device_is_new=self.device_is_new,
            accessed_at=self.accessed_at,
            after_hours=self.after_hours,
        )


class ContextSnapshotBody(BaseModel):
    """The stored snapshot, returned as structured fields rather than opaque JSON."""

    actor_user_id: UUID
    device_id: str
    device_is_new: bool
    accessed_at: datetime
    after_hours: bool


class RiskScoreResponse(BaseModel):
    """One persisted contextual risk computation."""

    # ``model_version`` is the SPEC.md contract; Pydantic otherwise warns on
    # any field beginning with ``model_``. Same override as ClassificationResponse.
    model_config = ConfigDict(protected_namespaces=())

    id: UUID
    document_id: UUID
    risk_value: Decimal
    model_version: str
    context_snapshot: ContextSnapshotBody
    computed_at: datetime

    @classmethod
    def from_row(
        cls,
        *,
        risk_score_id: UUID,
        document_id: UUID,
        result: RiskScoreResult,
        computed_at: datetime,
    ) -> "RiskScoreResponse":
        """Build a response from the persisted row and the scoring result."""
        snap = result.snapshot
        return cls(
            id=risk_score_id,
            document_id=document_id,
            risk_value=result.risk_value,
            model_version=result.model_version,
            context_snapshot=ContextSnapshotBody(
                actor_user_id=snap.actor_user_id,
                device_id=snap.device_id,
                device_is_new=snap.device_is_new,
                accessed_at=snap.accessed_at,
                after_hours=snap.after_hours,
            ),
            computed_at=computed_at,
        )
